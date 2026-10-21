from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import admin_user, current_user
from ..models import User
from ..schemas import DEFAULT_SETTINGS, REGULATORS

router = APIRouter(prefix="/settings")


class SettingsIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    regulators: list[str] = []
    reminders: bool = True
    changes: bool = True
    weekly: bool = False
    default_lead: int = Field(default=3, ge=0, le=30)

    @field_validator("regulators")
    @classmethod
    def known(cls, v):
        return [r for r in dict.fromkeys(v) if r in REGULATORS]


def _out(user: User) -> dict:
    return {"name": user.workspace.name, **{**DEFAULT_SETTINGS, **(user.workspace.settings or {})}}


@router.get("")
def get_settings(user: User = Depends(current_user)):
    return _out(user)


@router.put("")
def put_settings(body: SettingsIn, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    user.workspace.name = body.name.strip()
    user.workspace.settings = body.model_dump(exclude={"name"})  # reassign => SQLAlchemy sees the JSON change
    db.commit()
    return _out(user)
