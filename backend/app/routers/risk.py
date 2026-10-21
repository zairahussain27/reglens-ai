from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Assessment, Finding, Risk, User
from ..services import metrics
from ..utils import iso

router = APIRouter(prefix="/risk")
LEVELS = {"Low", "Medium", "High"}
STATUSES = {"Open", "In progress", "Resolved"}


class RiskIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    area: str = Field(default="Reporting", min_length=1, max_length=60)
    level: str = "Medium"
    due: date | None = None
    owner_id: int | None = None


class RiskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=300)
    area: str | None = Field(default=None, min_length=1, max_length=60)
    level: str | None = None
    status: str | None = None
    ignored: bool | None = None
    due: date | None = None
    owner_id: int | None = None


def out(r: Risk) -> dict:
    return {"id": r.id, "title": r.title, "area": r.area, "level": r.level, "status": r.status, "source": r.source,
            "owner": r.owner.name if r.owner else "", "owner_id": r.owner_id, "due": iso(r.due), "ignored": r.ignored}


def _check(db: Session, user: User, level, status, owner_id) -> None:
    if level is not None and level not in LEVELS:
        raise HTTPException(422, "Choose a valid level")
    if status is not None and status not in STATUSES:
        raise HTTPException(422, "Choose a valid status")
    if owner_id is not None:
        owner = db.get(User, owner_id)
        if not owner or owner.workspace_id != user.workspace_id:
            raise HTTPException(422, "Owner must be a member of this workspace")


@router.get("")
def overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = metrics.risk_summary(db, user.workspace_id)
    assessment = metrics.latest_assessment(db, user.workspace_id)
    assessment_risk = metrics.risk_details(assessment.findings) if assessment else None
    finding_by_regulation = {f"finding:{f.regulation_id}": f for f in assessment.findings} if assessment else {}
    members = db.scalars(select(User).where(User.workspace_id == user.workspace_id).order_by(User.name))
    register = []
    for risk in s["rows"]:
        item = out(risk)
        finding = finding_by_regulation.get(risk.source_ref) if risk.source_ref else None
        if finding:
            item["classification"] = "confirmed" if finding.compliance_status in {"Non-Compliant", "Partially Compliant"} else "review"
            item["compliance_status"] = finding.compliance_status or "Unable to Determine"
            item["applicability"] = finding.applicability or "Unknown"
        else:
            item["classification"] = "confirmed" if risk.source == "Manual" else "review"
        register.append(item)
    return {"overall": s["overall"], "open": s["open"], "overdue": s["overdue"], "resolved": s["resolved"],
            "by_area": s["by_area"], "register": register,
            "assessment": {"risk_score": assessment_risk["score"], "risk_level": assessment_risk["level"],
                           "created_at": iso(assessment.created_at), "estimated": assessment_risk["estimated"],
                           "applicable_count": assessment_risk["applicable_count"],
                           "unknown_applicability_count": assessment_risk["unknown_count"],
                           "unassessed_count": assessment_risk["unassessed_count"],
                           "contributors": assessment_risk["contributors"],
                           "formula": assessment_risk["formula"]} if assessment and assessment_risk else None,
            "members": [{"id": m.id, "name": m.name} for m in members]}


@router.post("")
def create(body: RiskIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _check(db, user, body.level, None, body.owner_id)
    r = Risk(workspace_id=user.workspace_id, title=body.title.strip(), area=body.area.strip(), level=body.level,
             due=body.due, owner_id=body.owner_id or user.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return out(r)


def _get(db: Session, user: User, rid: int) -> Risk:
    r = db.get(Risk, rid)
    if not r or r.workspace_id != user.workspace_id:
        raise HTTPException(404, "Risk not found")
    return r


@router.patch("/{rid}")
def patch(rid: int, body: RiskPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = _get(db, user, rid)
    data = body.model_dump(exclude_unset=True)
    _check(db, user, data.get("level"), data.get("status"), data.get("owner_id"))
    for k, v in data.items():
        if v is not None or k in {"due", "owner_id"}:
            setattr(r, k, v.strip() if isinstance(v, str) else v)
    db.commit()
    db.refresh(r)
    return out(r)


@router.delete("/{rid}", status_code=204)
def delete(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_get(db, user, rid))
    db.commit()
