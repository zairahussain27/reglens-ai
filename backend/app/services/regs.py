"""Regulation ingestion (upload / URL / seed directory)."""
import re
import uuid
import hashlib
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Regulation
from . import ingest

settings = get_settings()


def ingest_regulation(db: Session, reg: Regulation, data: bytes, filename: str) -> None:
    try:
        pages = ingest.extract(data, filename)
        reg.summary = ingest.summarise(pages)
        ingest.index_source(db, "regulation", reg.id, reg.workspace_id, reg.title, pages)
        reg.status, reg.ingestion_error = "ready", None
    except ingest.ExtractionError as exc:
        ingest.drop_source(db, "regulation", reg.id)
        reg.status, reg.ingestion_error = "failed", str(exc)
    db.commit()


def seed_directory(db: Session, include_pdfs: bool = True) -> int:
    """Idempotently load platform-wide text and PDF regulations from the seed directory."""
    added = 0
    existing = set(db.scalars(select(Regulation.title).where(Regulation.workspace_id.is_(None))))
    digests: set[str] = set()
    paths = sorted(settings.seed_dir.glob("*.txt"))
    if include_pdfs:
        paths.extend(sorted(settings.seed_dir.glob("*.pdf")))
    for path in paths:
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest in digests:
            continue
        digests.add(digest)

        meta: dict[str, str] = {}
        if path.suffix.lower() == ".txt":
            raw = data.decode("utf-8").replace("\r\n", "\n")
            head, _, body = raw.partition("\n\n")
            meta = {k.strip().lower(): v.strip() for k, _, v in
                    (ln.partition(":") for ln in head.splitlines()) if v}
            data = body.encode("utf-8")
            if not body.strip():
                continue
        else:
            body = ""

        title = meta.get("title") or re.sub(r"^\d+[_ -]*", "", path.stem).replace("_", " ").replace("-", " ").strip()
        title = title[:300]
        if title in existing:
            continue
        issued = None
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta.get("issued", "")):
            issued = date.fromisoformat(meta["issued"])
        regulator = meta.get("regulator")
        if not regulator:
            filename = path.name.lower()
            regulator = "RBI" if "rbi" in filename else "SEBI" if "sebi" in filename else "CBIC / GST" if "cgst" in filename or "gst" in filename else "Other"
        stored = f"{uuid.uuid4().hex}{path.suffix.lower()}"
        (settings.upload_dir / stored).write_bytes(data)
        reg = Regulation(workspace_id=None, title=title, regulator=regulator, issued_on=issued,
                         source_url=meta.get("source"), file_path=stored, file_name=f"{title}{path.suffix.lower()}")
        db.add(reg)
        db.flush()
        ingest_regulation(db, reg, data, path.name)
        existing.add(title)
        added += 1
    return added
