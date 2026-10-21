"""In-memory BM25 over chunks, cached per workspace and invalidated whenever the corpus changes."""
import math
import re
import threading
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import Chunk, Document, Regulation

STOP = set("a an and are as at be been by for from has have how i in is it its of on or that the this to was what when where which who will with you your can do does should must may any if not than then there their they we our us about into over under per".split())
K1, B = 1.5, 0.75
_TOKEN = re.compile(r"[a-z0-9]+")

_lock = threading.Lock()
_version = 0
_cache: dict[int, "Index"] = {}


def _stem(t: str) -> str:
    for suf in ("ations", "ation", "ings", "ing", "ies", "es", "ed", "s"):
        if len(t) > len(suf) + 3 and t.endswith(suf):
            return t[: -len(suf)] + ("y" if suf == "ies" else "")
    return t


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN.findall(text.lower()) if t not in STOP and len(t) > 1]


@dataclass
class Hit:
    chunk_id: int
    title: str
    page: int | None
    text: str
    score: float


@dataclass
class Index:
    chunks: list = field(default_factory=list)
    tfs: list = field(default_factory=list)
    lens: list = field(default_factory=list)
    df: dict = field(default_factory=dict)
    avg_len: float = 1.0

    def search(self, query: str, k: int = 5) -> list[Hit]:
        q = set(tokenize(query))
        if not q or not self.chunks:
            return []
        n = len(self.chunks)
        scored: list[tuple[float, int]] = []
        for i, tf in enumerate(self.tfs):
            s = 0.0
            for term in q:
                f = tf.get(term)
                if not f:
                    continue
                idf = math.log(1 + (n - self.df[term] + 0.5) / (self.df[term] + 0.5))
                s += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * self.lens[i] / self.avg_len))
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        return [Hit(self.chunks[i].id, self.chunks[i].title, self.chunks[i].page, self.chunks[i].text, s)
                for s, i in scored[:k]]


def invalidate() -> None:
    global _version
    with _lock:
        _version += 1
        _cache.clear()


def _build(db: Session, workspace_id: int) -> Index:
    ready_regs = select(Regulation.id).where(
        Regulation.status == "ready", or_(Regulation.workspace_id.is_(None), Regulation.workspace_id == workspace_id))
    ai_docs = select(Document.id).where(
        Document.workspace_id == workspace_id, Document.use_in_ai.is_(True), Document.status == "ready")
    chunks = db.scalars(select(Chunk).where(or_(
        (Chunk.source_type == "regulation") & Chunk.source_id.in_(ready_regs),
        (Chunk.source_type == "document") & Chunk.source_id.in_(ai_docs)))).all()
    idx = Index(chunks=list(chunks))
    for c in chunks:
        toks = tokenize(c.title + " " + c.text)
        tf: dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        idx.tfs.append(tf)
        idx.lens.append(len(toks) or 1)
        for t in tf:
            idx.df[t] = idx.df.get(t, 0) + 1
    idx.avg_len = (sum(idx.lens) / len(idx.lens)) if idx.lens else 1.0
    return idx


def get_index(db: Session, workspace_id: int) -> Index:
    with _lock:
        cached, version = _cache.get(workspace_id), _version
    if cached is not None:
        return cached
    idx = _build(db, workspace_id)
    with _lock:
        if version == _version:  # don't cache an index built from a corpus that changed meanwhile
            _cache[workspace_id] = idx
    return idx


def vector_search(db: Session, query: str, workspace_id: int, k: int = 5) -> list[Hit] | None:
    from . import vector_store
    if not vector_store.enabled():
        return None
    try:
        points = vector_store.search(query, workspace_id, k)
    except Exception as exc:
        import logging
        logging.getLogger("reglens.retrieval").warning("Qdrant search unavailable: %s", exc)
        return None
    ids = [int(p.payload["chunk_id"]) for p in points if p.payload and p.payload.get("chunk_id")]
    if not ids:
        # Ignore stale or unlinked Qdrant entries and use the SQL-backed index instead.
        return None
    rows = {c.id: c for c in db.scalars(select(Chunk).where(Chunk.id.in_(ids))).all()}
    hits = [Hit(rows[chunk_id].id, rows[chunk_id].title, rows[chunk_id].page, rows[chunk_id].text, float(point.score))
            for point in points if point.payload and point.payload.get("chunk_id")
            for chunk_id in [int(point.payload["chunk_id"])] if chunk_id in rows]
    return hits or None
