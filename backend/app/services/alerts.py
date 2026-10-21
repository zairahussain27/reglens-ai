"""Turns due reminders and risks into in-app alerts. Idempotent via dedupe keys."""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Alert, Reminder, Risk
from ..utils import iso


def push(db: Session, workspace_id: int, title: str, detail: str, key: str | None) -> bool:
    if key and db.scalar(select(Alert.id).where(Alert.workspace_id == workspace_id, Alert.dedupe_key == key)):
        return False
    db.add(Alert(workspace_id=workspace_id, title=title, detail=detail, dedupe_key=key))
    return True


def sync(db: Session, workspace_id: int) -> None:
    today = date.today()
    created = False
    for r in db.scalars(select(Reminder).where(Reminder.workspace_id == workspace_id, Reminder.done.is_(False))):
        if r.due - timedelta(days=r.lead) <= today:
            when = "is overdue" if r.due < today else ("is due today" if r.due == today else f"is due on {iso(r.due)}")
            created |= push(db, workspace_id, f"Reminder: {r.title}", f"This task {when}.", f"rem:{r.id}:{iso(r.due)}")
    for r in db.scalars(select(Risk).where(Risk.workspace_id == workspace_id, Risk.status != "Resolved",
                                           Risk.due.is_not(None), Risk.due < today)):
        created |= push(db, workspace_id, f"Risk overdue: {r.title}", f"Was due on {iso(r.due)}.", f"risk:{r.id}:over")
    if created:
        db.commit()
