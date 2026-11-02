from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Assessment, Filing, Reminder, Report, User
from ..services import ai_client, alerts, metrics, scoring
from ..services.company import evaluate, profile_status
from ..utils import iso
from .regulations import visible

router = APIRouter()


def _deadlines(db: Session, wid: int) -> list[dict]:
    horizon, today = date.today() + timedelta(days=30), date.today()
    items = []
    for f in db.scalars(select(Filing).where(Filing.workspace_id == wid, Filing.status == "Pending",
                                             Filing.due_on.is_not(None), Filing.due_on <= horizon)):
        items.append({"kind": "filing", "title": f"{f.kind} {f.period}".strip(), "due": iso(f.due_on),
                      "overdue": f.due_on < today, "days": (f.due_on - today).days})
    for r in db.scalars(select(Reminder).where(Reminder.workspace_id == wid, Reminder.done.is_(False),
                                               Reminder.due <= horizon)):
        items.append({"kind": "reminder", "title": r.title, "due": iso(r.due), "overdue": r.due < today,
                      "days": (r.due - today).days})
    return sorted(items, key=lambda i: i["days"])[:8]


@router.get("/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    wid = user.workspace_id
    alerts.sync(db, wid)
    company = metrics.get_company(db, wid)
    status = profile_status(company.data, company.dismissed)
    a = metrics.latest_assessment(db, wid)
    regs = visible(db, wid, only_ready=True)
    verdicts = {r.id: evaluate(r.regulator, company.data)[0] == "Applicable" for r in regs}
    followed = (user.workspace.settings or {}).get("regulators") or []
    feed = [r for r in regs if not followed or r.regulator in followed or r.regulator == "Other"][:8]
    rs = metrics.risk_summary(db, wid)
    summary = scoring.compliance_summary(a.findings) if a else None
    risk = metrics.risk_details(a.findings) if a else None
    trend_rows = list(db.scalars(select(Assessment).where(Assessment.workspace_id == wid)
                                 .order_by(Assessment.id.desc()).limit(6)))[::-1]
    scorecards = []
    if a:
        for f in a.findings:
            if f.applicability == "Applicable":
                s = summary["by_finding"].get(f.id, {})
                scorecards.append({"id": f.id, "title": f.title, "status": f.compliance_status, "score": s.get("score"),
                                   "assessed": s.get("assessed", 0), "total": s.get("total", 0)})
    reason = None
    if summary and summary["score"] is None:
        reason = summary["reason"]
    elif not a:
        reason = "Create an assessment and let AI evaluate your applicable regulations to get your compliance score."
    db.commit()
    return {
        "profile": {**status, "review_required": bool(a and company.updated_at > a.created_at)},
        "ai": ai_client.status(),
        "applicable_regulations": (a.counts or {}).get("applicable", 0) if a else sum(verdicts.values()),
        "unknown_applicability": (a.counts or {}).get("unknown", 0) if a else 0,
        "compliance_score": summary["score"] if summary else None,
        "compliance_estimated": bool(summary and summary["basis"] == "provisional"),
        "compliance_score_reason": reason,
        "coverage": summary["coverage"] if summary else None,
        "confidence": summary["confidence"] if summary else None,
        "assessed_obligations": summary["assessed"] if summary else 0,
        "total_obligations": summary["total"] if summary else 0,
        "waiting_for_ai": summary["waiting"] if summary else 0,
        "compliance_assessments": len(trend_rows),
        "assessment_status": a.status if a else None,
        "assessment_id": a.id if a else None,
        "risk_score": risk["score"] if risk else None,
        "risk_level": risk["level"] if risk else None,
        "risk_estimated": bool(risk and risk["estimated"]),
        "risk_unknown_applicability": risk["unknown_count"] if risk else 0,
        "risk_unassessed_findings": risk["unassessed_count"] if risk else 0,
        "open": rs["open"], "overdue": rs["overdue"], "by_area": rs["by_area"],
        "regulations": len(regs),
        "reports": db.scalar(select(func.count()).select_from(Report).where(Report.workspace_id == wid)),
        "trend": [{"id": t.id, "date": iso(t.created_at), "compliance": t.compliance_score, "risk": t.risk_score}
                  for t in trend_rows],
        "scorecards": scorecards,
        "priorities": scoring.action_plan(a.findings, 5) if a else [],
        "deadlines": _deadlines(db, wid),
        "latest": [{"id": r.id, "title": r.title, "regulator": r.regulator, "date": iso(r.issued_on or r.created_at),
                    "applicable": verdicts[r.id]} for r in feed],
        "assessment": {"created_at": iso(a.created_at), "counts": a.counts} if a else None,
    }