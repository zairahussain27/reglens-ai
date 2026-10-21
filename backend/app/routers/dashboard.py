from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Assessment, Report, User
from ..services import alerts, metrics
from ..services.company import evaluate, profile_status
from ..utils import iso
from .regulations import visible

router = APIRouter()


@router.get("/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    wid = user.workspace_id
    alerts.sync(db, wid)
    company = metrics.get_company(db, wid)
    status = profile_status(company.data, company.dismissed)
    a = metrics.latest_assessment(db, wid)
    scores = db.scalars(select(Assessment.compliance_score).where(
        Assessment.workspace_id == wid, Assessment.compliance_score.is_not(None)
    )).all()
    average_compliance = round(sum(scores) / len(scores), 1) if scores else None
    regs = visible(db, wid, only_ready=True)
    verdicts = {r.id: evaluate(r.regulator, company.data)[0] == "Applicable" for r in regs}
    followed = (user.workspace.settings or {}).get("regulators") or []
    feed = [r for r in regs if not followed or r.regulator in followed or r.regulator == "Other"][:8]
    rs = metrics.risk_summary(db, wid)
    db.commit()
    return {
        "profile": {**status, "review_required": bool(a and company.updated_at > a.created_at)},
        "applicable_regulations": (a.counts or {}).get("applicable", 0) if a else sum(verdicts.values()),
        "unknown_applicability": (a.counts or {}).get("unknown", 0) if a else 0,
        "compliance_score": average_compliance,
        "compliance_assessments": len(scores),
        "risk_score": a.risk_score if a else None,
        "risk_estimated": bool(a and metrics.risk_details(a.findings)["estimated"]),
        "risk_unknown_applicability": metrics.risk_details(a.findings)["unknown_count"] if a else 0,
        "risk_unassessed_findings": metrics.risk_details(a.findings)["unassessed_count"] if a else 0,
        "open": rs["open"], "overdue": rs["overdue"], "by_area": rs["by_area"],
        "regulations": len(regs),
        "reports": db.scalar(select(func.count()).select_from(Report).where(Report.workspace_id == wid)),
        "latest": [{"id": r.id, "title": r.title, "regulator": r.regulator, "date": iso(r.issued_on or r.created_at),
                    "applicable": verdicts[r.id]} for r in feed],
        "assessment": {"created_at": iso(a.created_at), "counts": a.counts} if a else None,
    }
