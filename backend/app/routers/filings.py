import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Filing, User
from ..utils import file_response, fy_of, iso, parse_date, remove_file, save_upload

router = APIRouter(prefix="/filings")
KINDS = ["GST - GSTR-1", "GST - GSTR-3B", "GST - Annual return (GSTR-9)", "TDS return", "Advance tax", "Income tax return",
         "PF / ESI", "Professional tax", "ROC annual filing", "Other"]
STATUSES = {"Pending", "Filed", "Paid"}


def _amount(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise HTTPException(422, "Amount must be a number")
    if v < 0 or v > 1e12:
        raise HTTPException(422, "Amount is out of range")
    return round(v, 2)


def out(f: Filing) -> dict:
    ref = f.due_on or f.paid_on or f.created_at.date()
    return {"id": f.id, "kind": f.kind, "period": f.period, "due_on": iso(f.due_on), "paid_on": iso(f.paid_on),
            "amount": f.amount, "status": f.status, "reference": f.reference, "notes": f.notes,
            "has_file": bool(f.file_path), "file_name": f.file_name, "fy": fy_of(ref),
            "overdue": f.status == "Pending" and bool(f.due_on) and f.due_on < date.today()}


def _rows(db: Session, wid: int) -> list[Filing]:
    return list(db.scalars(select(Filing).where(Filing.workspace_id == wid).order_by(Filing.due_on.is_(None), Filing.due_on.desc(), Filing.id.desc())))


@router.get("")
def list_filings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = [out(f) for f in _rows(db, user.workspace_id)]
    done = [i for i in items if i["status"] in {"Filed", "Paid"}]
    by_kind: dict[str, float] = {}
    for i in done:
        by_kind[i["kind"]] = by_kind.get(i["kind"], 0) + (i["amount"] or 0)
    return {"items": items, "kinds": KINDS, "fys": sorted({i["fy"] for i in items}, reverse=True),
            "summary": {"paid_total": sum(i["amount"] or 0 for i in done), "pending": sum(i["status"] == "Pending" for i in items),
                        "overdue": sum(i["overdue"] for i in items), "by_kind": [{"kind": k, "paid": v} for k, v in by_kind.items()]}}


@router.post("")
def create(kind: str = Form(...), period: str = Form(""), due_on: str = Form(""), status: str = Form("Pending"),
           amount: str = Form(""), paid_on: str = Form(""), reference: str = Form(""), notes: str = Form(""),
           file: UploadFile | None = File(default=None), user: User = Depends(current_user), db: Session = Depends(get_db)):
    if kind not in KINDS:
        raise HTTPException(422, "Choose a valid filing type")
    if status not in STATUSES:
        raise HTTPException(422, "Choose a valid status")
    paid = parse_date(paid_on)
    if status in {"Filed", "Paid"} and not paid:
        paid = date.today()
    stored = name = None
    if file is not None and file.filename:
        stored, name, _ = save_upload(file, {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".csv", ".xlsx"})
    f = Filing(workspace_id=user.workspace_id, kind=kind, period=period.strip()[:80], due_on=parse_date(due_on),
               paid_on=paid if status != "Pending" else None, amount=_amount(amount), status=status,
               reference=reference.strip()[:160], notes=notes.strip()[:2000], file_path=stored, file_name=name)
    db.add(f)
    db.commit()
    return out(f)


class FilingPatch(BaseModel):
    status: str | None = None
    period: str | None = None
    due_on: str | None = None
    paid_on: str | None = None
    amount: float | None = None
    reference: str | None = None
    notes: str | None = None


def _get(db: Session, user: User, fid: int) -> Filing:
    f = db.get(Filing, fid)
    if not f or f.workspace_id != user.workspace_id:
        raise HTTPException(404, "Filing not found")
    return f


@router.get("/export/csv")
def export_csv(fy: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Type", "Period", "Financial year", "Status", "Due on", "Paid on", "Amount (INR)", "Reference", "Notes"])
    safe = lambda v: "'" + v if isinstance(v, str) and v[:1] in "=+-@\t\r" else v  # noqa: E731  (CSV formula injection)
    for f in _rows(db, user.workspace_id):
        o = out(f)
        if fy and o["fy"] != fy:
            continue
        w.writerow([safe(x) for x in [f.kind, f.period, o["fy"], f.status, iso(f.due_on) or "", iso(f.paid_on) or "",
                                       "" if f.amount is None else f.amount, f.reference, f.notes]])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="filings.csv"'})


@router.patch("/{fid}")
def patch(fid: int, body: FilingPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    f = _get(db, user, fid)
    data = body.model_dump(exclude_unset=True)
    if "status" in data:
        if data["status"] not in STATUSES:
            raise HTTPException(422, "Choose a valid status")
        f.status = data["status"]
        if f.status == "Pending":
            f.paid_on = None
        elif not f.paid_on and "paid_on" not in data:
            f.paid_on = date.today()
    if "due_on" in data:
        f.due_on = parse_date(data["due_on"])
    if "paid_on" in data:
        f.paid_on = parse_date(data["paid_on"])
    if "amount" in data:
        f.amount = _amount(data["amount"])
    for k in ("period", "reference", "notes"):
        if k in data and data[k] is not None:
            setattr(f, k, data[k].strip())
    db.commit()
    return out(f)


@router.delete("/{fid}", status_code=204)
def delete(fid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    f = _get(db, user, fid)
    remove_file(f.file_path)
    db.delete(f)
    db.commit()


@router.get("/{fid}/file")
def proof(fid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    f = _get(db, user, fid)
    return file_response(f.file_path, f.file_name or "proof")
