from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Alert, Assessment, Regulation, User
from ..services import alerts
from ..services import metrics
from ..utils import iso
from .regulations import visible

router = APIRouter(prefix="/alerts")


def out(a: Alert) -> dict:
    return {"id": a.id, "title": a.title, "detail": a.detail, "created_at": iso(a.created_at), "unread": a.unread}


@router.get("")
def list_alerts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    alerts.sync(db, user.workspace_id)
    rows = db.scalars(select(Alert).where(Alert.workspace_id == user.workspace_id).order_by(Alert.id.desc()).limit(200))
    return [out(a) for a in rows]


@router.get("/summary")
def summary(user: User = Depends(current_user), db: Session = Depends(get_db)):
    alerts.sync(db, user.workspace_id)
    wid = user.workspace_id
    notifications = [
        {"id": f"alert-{a.id}", "kind": "alert", "title": a.title, "detail": a.detail,
         "created_at": iso(a.created_at), "unread": a.unread}
        for a in db.scalars(select(Alert).where(Alert.workspace_id == wid).order_by(Alert.id.desc()).limit(100))
    ]
    notifications.extend(
        {"id": f"reg-{r.id}", "kind": "regulation", "title": f"New regulation added: {r.title}",
         "detail": f"{r.regulator} · {r.status}", "created_at": iso(r.created_at), "unread": False}
        for r in visible(db, wid)[:50]
    )
    assessments = db.scalars(select(Assessment).where(Assessment.workspace_id == wid)
                             .order_by(Assessment.id.desc()).limit(30)).all()
    for assessment in assessments:
        notifications.append({"id": f"assessment-{assessment.id}", "kind": "assessment",
                              "title": f"Assessment #{assessment.id} { 'completed' if assessment.status == 'complete' else 'created' }",
                              "detail": f"Compliance {assessment.compliance_score if assessment.compliance_score is not None else 'n/a'}% · Risk {assessment.risk_score if assessment.risk_score is not None else 'n/a'}%",
                              "created_at": iso(assessment.created_at), "unread": False})
    for assessment in assessments:
        for finding in assessment.findings:
            if finding.applicability == "Applicable":
                notifications.append({"id": f"applicable-{assessment.id}-{finding.id}", "kind": "risk",
                                      "title": f"Risk identified: {finding.title}",
                                      "detail": f"Marked applicable in assessment #{assessment.id} · {finding.severity} severity",
                                      "created_at": iso(assessment.created_at), "unread": False})
    latest = metrics.latest_assessment(db, wid)
    if latest:
        notifications.append({"id": f"risk-score-{latest.id}", "kind": "risk-score",
                              "title": "Risk score updated",
                              "detail": f"{latest.risk_score if latest.risk_score is not None else 'n/a'}% · Assessment #{latest.id}",
                              "created_at": iso(latest.created_at), "unread": False})
    notifications.sort(key=lambda item: (item["created_at"] or "", item["id"]), reverse=True)
    unread_count = sum(1 for item in notifications if item["kind"] == "alert" and item["unread"])
    return {"items": notifications[:150], "unread": unread_count}


@router.get("/unread-count")
def unread(user: User = Depends(current_user), db: Session = Depends(get_db)):
    alerts.sync(db, user.workspace_id)
    n = db.scalar(select(func.count()).select_from(Alert).where(Alert.workspace_id == user.workspace_id, Alert.unread.is_(True)))
    return {"count": n}


@router.post("/read-all")
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(update(Alert).where(Alert.workspace_id == user.workspace_id).values(unread=False))
    db.commit()
    return {"ok": True}


@router.post("/{aid}/read")
def read_one(aid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(Alert, aid)
    if not a or a.workspace_id != user.workspace_id:
        raise HTTPException(404, "Alert not found")
    a.unread = False
    db.commit()
    return out(a)
