"""Text extraction + chunking. Turns PDFs / TXT / HTML into searchable Chunk rows."""
import io
import logging
import re
from html.parser import HTMLParser

from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import Chunk
from . import retrieval, vector_store

log = logging.getLogger("reglens.ingest")

CHUNK_CHARS = 900
OVERLAP_CHARS = 150


class ExtractionError(Exception):
    pass


def extract_pdf(data: bytes) -> list[tuple[int, str]]:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        pages = [(i + 1, (p.extract_text() or "")) for i, p in enumerate(reader.pages)]
    except Exception as exc:  # pypdf raises many types on corrupt files
        raise ExtractionError(f"Could not read the PDF ({type(exc).__name__})") from exc
    pages = [(n, clean(t)) for n, t in pages if t.strip()]
    if not pages:
        raise ExtractionError("No extractable text found. Scanned PDFs need OCR before upload.")
    return pages


def extract_text_file(data: bytes) -> list[tuple[int, str]]:
    text = ""
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeError:
            continue
    text = clean(text)
    if not text:
        raise ExtractionError("The file has no text")
    return [(1, text)]


class _HTMLText(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in {"p", "br", "li", "h1", "h2", "h3", "h4", "tr", "div"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def extract_html(data: bytes) -> list[tuple[int, str]]:
    parser = _HTMLText()
    parser.feed(data.decode("utf-8", errors="ignore"))
    text = clean("".join(parser.parts))
    if len(text) < 80:
        raise ExtractionError("The page has no readable text")
    return [(1, text)]


def extract(data: bytes, filename: str) -> list[tuple[int, str]]:
    name = filename.lower()
    if name.endswith(".pdf") or data[:5] == b"%PDF-":
        return extract_pdf(data)
    if name.endswith((".html", ".htm")):
        return extract_html(data)
    return extract_text_file(data)


def clean(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_pages(pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Split each page into ~900 char passages on sentence boundaries with a small overlap."""
    out: list[tuple[int, str]] = []
    for page, text in pages:
        sentences = re.split(r"(?<=[.!?;:])\s+|\n{2,}", text)
        buf = ""
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if buf and len(buf) + len(s) + 1 > CHUNK_CHARS:
                out.append((page, buf))
                buf = buf[-OVERLAP_CHARS:].split(" ", 1)[-1] + " " + s
            else:
                buf = f"{buf} {s}".strip()
        if buf:
            out.append((page, buf))
    return out


def summarise(pages: list[tuple[int, str]], limit: int = 300) -> str:
    text = " ".join(t for _, t in pages[:2])
    text = re.sub(r"\s+", " ", text).strip()
    summary = ""
    for s in re.split(r"(?<=[.!?])\s+", text):
        if len(s) < 25:
            continue
        if len(summary) + len(s) > limit:
            break
        summary = f"{summary} {s}".strip()
    return summary or text[:limit].rstrip() + ("…" if len(text) > limit else "")


def index_source(db: Session, source_type: str, source_id: int, workspace_id: int | None, title: str,
                 pages: list[tuple[int, str]]) -> int:
    """Replace all chunks for a source in one bulk insert (fast, atomic with the caller's commit)."""
    db.execute(delete(Chunk).where(Chunk.source_type == source_type, Chunk.source_id == source_id))
    rows = [
        {"source_type": source_type, "source_id": source_id, "workspace_id": workspace_id,
         "title": title, "page": page, "text": text}
        for page, text in chunk_pages(pages)
    ]
    if rows:
        db.execute(Chunk.__table__.insert(), rows)
        db.flush()
        stored = db.scalars(select(Chunk).where(
            Chunk.source_type == source_type, Chunk.source_id == source_id)).all()
        if vector_store.enabled():
            try:
                vector_store.upsert_chunks([
                    {"id": c.id, "source_type": c.source_type, "source_id": c.source_id,
                     "workspace_id": c.workspace_id, "title": c.title, "text": c.text}
                    for c in stored
                ])
            except Exception:
                # Keep the SQL corpus available to BM25 if embeddings or Qdrant are down.
                log.exception("Qdrant indexing failed for %s %s; retaining SQL chunks", source_type, source_id)
    retrieval.invalidate()
    return len(rows)


def drop_source(db: Session, source_type: str, source_id: int) -> None:
    db.execute(delete(Chunk).where(Chunk.source_type == source_type, Chunk.source_id == source_id))
    if vector_store.enabled():
        vector_store.delete_source(source_type, source_id)
    retrieval.invalidate()
