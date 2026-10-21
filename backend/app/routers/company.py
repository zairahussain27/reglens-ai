import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Document, User, utcnow
from ..services import metrics
from ..services.company import (GSTIN_RE, INT_FIELDS, LIST_FIELDS, OPTIONS, PAN_RE, REG_REQUIRED, REG_STATUS,
                                TEXT_FIELDS, profile_status)
from ..utils import parse_date

router = APIRouter(prefix="/company")
CHOICES = {"country": "countries", "entity_type": "entity_types", "state": "states", "turnover": "turnover",
           "employees": "employees", "operations_scope": "operations_scopes", "customer_type": "customer_types",
           "supply_type": "supply_types", "import_export": "yes_no_unknown", "regulated_financial": "yes_no_unknown",
           "listed_entity": "yes_no_unknown"}


def _list(value) -> list[str]:
    items = value.split(",") if isinstance(value, str) else (value or [])
    return [str(x).strip()[:80] for x in items if str(x).strip()][:30]


def clean(body: dict, db: Session, wid: int) -> dict:
    out: dict = {}
    for k in TEXT_FIELDS:
        v = str(body.get(k) or "").strip()
        if k in CHOICES and v and v not in OPTIONS[CHOICES[k]]:
            raise HTTPException(422, f"{k.replace('_', ' ').capitalize()}: choose one of the listed options")
        out[k] = v[: 2000 if k == "description" else 300]
    out["pan"], out["gstin"] = out["pan"].upper(), out["gstin"].upper()
    if out["pan"] and not PAN_RE.match(out["pan"]):
        raise HTTPException(422, "PAN must look like ABCDE1234F")
    if out["gstin"] and not GSTIN_RE.match(out["gstin"]):
        raise HTTPException(422, "GSTIN must be 15 characters, e.g. 22AAAAA0000A1Z5")
    for k in LIST_FIELDS:
        out[k] = _list(body.get(k))
    for k, lo, hi in (("established_year", 1800, date.today().year), ("branches", 0, 100000)):
        v = body.get(k)
        if v in (None, ""):
            out[k] = None
            continue
        try:
            n = int(v)
        except (TypeError, ValueError):
            raise HTTPException(422, f"{k.replace('_', ' ').capitalize()} must be a whole number")
        if not lo <= n <= hi:
            raise HTTPException(422, f"{k.replace('_', ' ').capitalize()} must be between {lo} and {hi}")
        out[k] = n
    regs = []
    for r in (body.get("registrations") or [])[:20]:
        rt = str(r.get("registration_type") or "").strip()
        if not rt:
            continue
        if rt not in OPTIONS["registration_types"]:
            raise HTTPException(422, "Choose a valid registration type")
        required, status = r.get("required_status") or "unknown", r.get("status") or "unknown"
        if required not in REG_REQUIRED or status not in REG_STATUS:
            raise HTTPException(422, "Invalid registration status")
        doc_id = r.get("document_id")
        if doc_id:
            doc = db.get(Document, int(doc_id))
            if not doc or doc.workspace_id != wid:
                raise HTTPException(422, f"Evidence document #{doc_id} was not found in your Library")
        regs.append({"registration_type": rt, "required_status": required, "status": status,
                     "number": str(r.get("number") or "")[:80], "document_id": int(doc_id) if doc_id else None,
                     "effective_date": parse_date(r.get("effective_date")).isoformat() if r.get("effective_date") else None,
                     "expiry_date": parse_date(r.get("expiry_date")).isoformat() if r.get("expiry_date") else None})
    out["registrations"] = regs
    return out


def _resp(c) -> dict:
    data = c.data or {}
    public_data = {key: value for key, value in data.items() if key != "_legal_name_change_used"}
    return {"company": public_data, "options": OPTIONS, "profile": profile_status(data, c.dismissed),
            "legal_name_change_used": bool(data.get("_legal_name_change_used", False))}


@router.get("")
def get_company(user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = metrics.get_company(db, user.workspace_id)
    db.commit()
    return _resp(c)


@router.put("")
def put_company(body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = metrics.get_company(db, user.workspace_id)
    previous = c.data or {}
    previous_name = str(previous.get("legal_name") or "").strip()
    updated = clean(body, db, user.workspace_id)
    updated_name = updated["legal_name"].strip()
    change_used = bool(previous.get("_legal_name_change_used", False))
    if previous_name and updated_name != previous_name:
        if change_used:
            raise HTTPException(403, "The one-time legal name change has already been used")
        change_used = True
    updated["_legal_name_change_used"] = change_used
    c.data = updated
    c.dismissed = str(body.get("save_for_later", "")).lower() == "true"
    c.updated_at = utcnow()
    db.commit()
    return _resp(c)
