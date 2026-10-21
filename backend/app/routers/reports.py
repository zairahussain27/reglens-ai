from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Report, User
from ..services import reports as svc
from ..utils import iso, safe_name

router = APIRouter(prefix="/reports")


class ReportIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    kind: str


def out(r: Report) -> dict:
    return {"id": r.id, "name": r.name, "kind": r.kind, "created_at": iso(r.created_at),
            "created_by_name": r.author.name if r.author else "Former member"}


@router.get("")
def list_reports(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [out(r) for r in db.scalars(select(Report).where(Report.workspace_id == user.workspace_id).order_by(Report.id.desc()))]


@router.post("")
def create(body: ReportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.kind not in svc.KINDS:
        raise HTTPException(422, "Choose a valid report type")
    r = Report(workspace_id=user.workspace_id, created_by=user.id, name=body.name.strip(), kind=body.kind,
               snapshot=svc.build_snapshot(db, user, body.kind))
    db.add(r)
    db.commit()
    db.refresh(r)
    return out(r)


@router.get("/{rid}/pdf")
def pdf(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(Report, rid)
    if not r or r.workspace_id != user.workspace_id:
        raise HTTPException(404, "Report not found")
    return Response(svc.render_pdf(r.name, r.snapshot), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{safe_name(r.name)}.pdf"'})
