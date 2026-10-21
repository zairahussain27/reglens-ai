from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import admin_user, current_user
from ..models import Regulation, User
from ..schemas import REGULATORS
from ..services import alerts, ingest, metrics, regs
from ..services.company import evaluate
from ..services.fetch import fetch
from ..utils import file_response, iso, parse_date, remove_file, safe_name, save_upload

router = APIRouter(prefix="/regulations")
settings = get_settings()


def visible(db: Session, wid: int, only_ready: bool = False) -> list[Regulation]:
    q = select(Regulation).where(or_(Regulation.workspace_id.is_(None), Regulation.workspace_id == wid))
    if only_ready:
        q = q.where(Regulation.status == "ready")
    return list(db.scalars(q.order_by(Regulation.issued_on.desc().nullslast(), Regulation.id.desc())))


def reg_out(r: Regulation, company: dict | None = None, wid: int | None = None) -> dict:
    out = {"id": r.id, "title": r.title, "regulator": r.regulator, "issued_on": iso(r.issued_on),
           "created_at": iso(r.created_at), "summary": r.summary, "status": r.status, "has_file": bool(r.file_path),
           "source_url": r.source_url, "ingestion_error": r.ingestion_error, "own": r.workspace_id is not None and r.workspace_id == wid}
    if company is not None:
        out["applicable"] = evaluate(r.regulator, company)[0] == "Applicable"
    return out


def _regulator(value: str) -> str:
    if value not in REGULATORS:
        raise HTTPException(422, "Choose a valid regulator")
    return value


def _announce(db: Session, user: User, reg: Regulation) -> None:
    if reg.status == "ready" and (user.workspace.settings or {}).get("changes", True):
        alerts.push(db, user.workspace_id, f"New regulation added: {reg.title}", f"{reg.regulator} regulation is now available in Ask.", f"reg:{reg.id}")
        db.commit()


@router.get("")
def list_regulations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    company = metrics.get_company(db, user.workspace_id).data
    return [reg_out(r, company, user.workspace_id) for r in visible(db, user.workspace_id)]


@router.post("")
def upload(file: UploadFile = File(...), title: str = Form(""), regulator: str = Form("Other"),
           issued_on: str = Form(""), user: User = Depends(admin_user), db: Session = Depends(get_db)):
    stored, original, data = save_upload(file, {".pdf", ".txt"})
    reg = Regulation(workspace_id=user.workspace_id, title=(title.strip() or original.rsplit(".", 1)[0])[:300],
                     regulator=_regulator(regulator), issued_on=parse_date(issued_on), file_path=stored, file_name=original)
    db.add(reg)
    db.flush()
    regs.ingest_regulation(db, reg, data, original)
    _announce(db, user, reg)
    return reg_out(reg, None, user.workspace_id)


class UrlIn(BaseModel):
    url: str = Field(max_length=1000)
    title: str | None = Field(default="", max_length=300)
    regulator: str = "Other"
    issued_on: str | None = None


@router.post("/from-url")
def from_url(body: UrlIn, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    data, _ctype, name = fetch(body.url.strip())
    stored = None
    ext = ".pdf" if data[:5] == b"%PDF-" else (".html" if name.lower().endswith((".html", ".htm")) else ".txt")
    if ext != ".html":  # keep downloadable copy for PDFs / text; HTML pages are indexed only
        stored = f"{__import__('uuid').uuid4().hex}{ext}"
        (settings.upload_dir / stored).write_bytes(data)
    reg = Regulation(workspace_id=user.workspace_id, title=((body.title or "").strip() or safe_name(name))[:300],
                     regulator=_regulator(body.regulator), issued_on=parse_date(body.issued_on), source_url=body.url.strip(),
                     file_path=stored, file_name=safe_name(name))
    db.add(reg)
    db.flush()
    regs.ingest_regulation(db, reg, data, name)
    _announce(db, user, reg)
    return reg_out(reg, None, user.workspace_id)


@router.post("/seed-ingest")
def seed_ingest(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    added = regs.seed_directory(db)
    db.commit()
    return {"added": added}


def _get(db: Session, wid: int, rid: int) -> Regulation:
    r = db.get(Regulation, rid)
    if not r or (r.workspace_id is not None and r.workspace_id != wid):
        raise HTTPException(404, "Regulation not found")
    return r


@router.delete("/{rid}", status_code=204)
def delete(rid: int, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    r = _get(db, user.workspace_id, rid)
    if r.workspace_id is None:
        raise HTTPException(403, "Platform regulations are managed by RegLens and cannot be deleted")
    ingest.drop_source(db, "regulation", r.id)
    remove_file(r.file_path)
    db.delete(r)
    db.commit()


@router.get("/{rid}/file")
def download(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = _get(db, user.workspace_id, rid)
    return file_response(r.file_path, r.file_name or f"{r.title}.pdf")
