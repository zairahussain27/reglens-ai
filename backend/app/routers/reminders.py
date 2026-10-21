from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Reminder, User
from ..utils import iso

router = APIRouter(prefix="/reminders")


class ReminderIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    due: date
    lead: int = Field(default=3, ge=0, le=30)


class ReminderPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    due: date | None = None
    lead: int | None = Field(default=None, ge=0, le=30)
    done: bool | None = None


def out(r: Reminder) -> dict:
    return {"id": r.id, "title": r.title, "due": iso(r.due), "lead": r.lead, "done": r.done}


def _get(db: Session, user: User, rid: int) -> Reminder:
    r = db.get(Reminder, rid)
    if not r or r.workspace_id != user.workspace_id:
        raise HTTPException(404, "Reminder not found")
    return r


@router.get("")
def list_reminders(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Reminder).where(Reminder.workspace_id == user.workspace_id).order_by(Reminder.done, Reminder.due))
    return [out(r) for r in rows]


@router.get("/open-count")
def open_count(user: User = Depends(current_user), db: Session = Depends(get_db)):
    count = db.scalar(select(func.count()).select_from(Reminder).where(
        Reminder.workspace_id == user.workspace_id, Reminder.done.is_(False)))
    return {"count": count or 0}


@router.post("")
def create(body: ReminderIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = Reminder(workspace_id=user.workspace_id, title=body.title.strip(), due=body.due, lead=body.lead)
    db.add(r)
    db.commit()
    return out(r)


@router.patch("/{rid}")
def patch(rid: int, body: ReminderPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = _get(db, user, rid)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(r, k, v.strip() if isinstance(v, str) else v)
    db.commit()
    return out(r)


@router.delete("/{rid}", status_code=204)
def delete(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_get(db, user, rid))
    db.commit()
