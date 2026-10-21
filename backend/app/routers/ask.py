from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import AskLog, Document, Regulation, User
from ..services import llm, retrieval
from ..utils import iso

router = APIRouter(prefix="/ask")


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


def log_out(a: AskLog) -> dict:
    return {"id": a.id, "question": a.question, "answer": a.answer, "sources": a.sources, "found": a.found,
            "created_at": iso(a.created_at)}


@router.get("/scope")
def scope(user: User = Depends(current_user), db: Session = Depends(get_db)):
    wid = user.workspace_id
    regs = db.scalar(select(func.count()).select_from(Regulation).where(
        Regulation.status == "ready", or_(Regulation.workspace_id.is_(None), Regulation.workspace_id == wid)))
    docs = db.scalar(select(func.count()).select_from(Document).where(
        Document.workspace_id == wid, Document.use_in_ai.is_(True), Document.status == "ready"))
    return {"regulations": regs, "library": docs}


@router.get("/history")
def history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(AskLog).where(AskLog.workspace_id == user.workspace_id).order_by(AskLog.id.desc()).limit(20))
    return [log_out(a) for a in rows]


@router.post("")
def ask(body: AskIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    question = body.question.strip()
    hits = retrieval.vector_search(db, question, user.workspace_id, k=5)
    if hits is None:
        hits = retrieval.get_index(db, user.workspace_id).search(question, k=5)
    text = llm.answer(question, hits)
    sources = [{"doc": h.title, "page": h.page, "snippet": h.text[:320] + ("…" if len(h.text) > 320 else "")} for h in hits[:5]]
    row = AskLog(workspace_id=user.workspace_id, user_id=user.id, question=question, answer=text, sources=sources, found=bool(hits))
    db.add(row)
    db.commit()
    return log_out(row)
