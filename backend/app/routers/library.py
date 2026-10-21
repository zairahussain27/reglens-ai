from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Document, User
from ..services import ingest, retrieval
from ..utils import file_response, iso, remove_file, save_upload

router = APIRouter(prefix="/documents")
KINDS = {"Policy", "Evidence", "Regulation", "Other"}


def doc_out(d: Document) -> dict:
    return {"id": d.id, "name": d.name, "kind": d.kind, "created_at": iso(d.created_at), "status": d.status,
            "use_in_ai": d.use_in_ai, "has_file": bool(d.file_path), "error": d.error}


def _get(db: Session, user: User, did: int) -> Document:
    d = db.get(Document, did)
    if not d or d.workspace_id != user.workspace_id:
        raise HTTPException(404, "Document not found")
    return d


@router.get("")
def list_docs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Document).where(Document.workspace_id == user.workspace_id).order_by(Document.id.desc()))
    return [doc_out(d) for d in rows]


@router.post("")
def upload(file: UploadFile = File(...), kind: str = Form("Other"), user: User = Depends(current_user),
           db: Session = Depends(get_db)):
    if kind not in KINDS:
        raise HTTPException(422, "Choose a valid category")
    stored, original, data = save_upload(file, {".pdf", ".txt"})
    doc = Document(workspace_id=user.workspace_id, uploaded_by=user.id, name=original, kind=kind, file_path=stored)
    db.add(doc)
    db.flush()
    try:
        pages = ingest.extract(data, original)
        ingest.index_source(db, "document", doc.id, doc.workspace_id, doc.name, pages)
        doc.status = "ready"
    except ingest.ExtractionError as exc:
        doc.status, doc.error = "failed", str(exc)
    db.commit()
    return doc_out(doc)


class DocPatch(BaseModel):
    use_in_ai: bool | None = None
    kind: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=300)


@router.patch("/{did}")
def patch(did: int, body: DocPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _get(db, user, did)
    if body.use_in_ai is not None:
        if body.use_in_ai and d.status != "ready":
            raise HTTPException(409, "This file has no searchable text, so it can't be used in Ask")
        d.use_in_ai = body.use_in_ai
        retrieval.invalidate()
    if body.kind is not None:
        if body.kind not in KINDS:
            raise HTTPException(422, "Choose a valid category")
        d.kind = body.kind
    if body.name:
        d.name = body.name.strip()
    db.commit()
    return doc_out(d)


@router.delete("/{did}", status_code=204)
def delete(did: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _get(db, user, did)
    ingest.drop_source(db, "document", d.id)
    remove_file(d.file_path)
    db.delete(d)
    db.commit()


@router.get("/{did}/file")
def download(did: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _get(db, user, did)
    return file_response(d.file_path, d.name)
