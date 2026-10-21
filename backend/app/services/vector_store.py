"""Qdrant storage for regulation and library chunk embeddings."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from qdrant_client import QdrantClient, models
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Chunk

if TYPE_CHECKING:
    from fastembed import TextEmbedding

log = logging.getLogger("reglens.vector_store")
settings = get_settings()


@lru_cache
def _embedding_model() -> TextEmbedding:
    if settings.embeddings != "fastembed":
        raise RuntimeError(f"Unsupported embeddings provider: {settings.embeddings}")
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=settings.embedding_model)


@lru_cache
def _client() -> QdrantClient:
    if not settings.qdrant_url or not settings.qdrant_api_key:
        raise RuntimeError("QDRANT_URL and QDRANT_API_KEY are required for vector retrieval")
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key,
                        timeout=settings.qdrant_timeout_seconds)


def enabled() -> bool:
    return bool(settings.qdrant_url and settings.qdrant_api_key)


def collection_info():
    return _client().get_collection(settings.qdrant_collection)


def _ensure_collection(vector_size: int) -> None:
    client = _client()
    if client.collection_exists(settings.qdrant_collection):
        return
    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
    )
    for field, schema in (("source_type", models.PayloadSchemaType.KEYWORD),
                          ("source_id", models.PayloadSchemaType.INTEGER),
                          ("workspace_id", models.PayloadSchemaType.INTEGER)):
        client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name=field,
            field_schema=schema,
            wait=True,
        )


def upsert_chunks(chunks: list[dict], batch_size: int = 32) -> None:
    if not chunks:
        return
    client = _client()
    collection_ready = False
    for offset in range(0, len(chunks), batch_size):
        batch = chunks[offset:offset + batch_size]
        vectors = list(_embedding_model().embed([c["title"] + "\n" + c["text"] for c in batch]))
        if not collection_ready:
            _ensure_collection(len(vectors[0]))
            collection_ready = True
        points = [
            models.PointStruct(
                id=c["id"],
                vector=vector.tolist(),
                payload={"chunk_id": c["id"], "source_type": c["source_type"],
                         "source_id": c["source_id"], "workspace_id": c["workspace_id"]},
            )
            for c, vector in zip(batch, vectors)
        ]
        client.upsert(collection_name=settings.qdrant_collection, points=points, wait=True)


def delete_source(source_type: str, source_id: int) -> None:
    if not enabled():
        return
    if not _client().collection_exists(settings.qdrant_collection):
        return
    _client().delete(
        collection_name=settings.qdrant_collection,
        points_selector=models.FilterSelector(
            filter=models.Filter(must=[
                models.FieldCondition(key="source_type", match=models.MatchValue(value=source_type)),
                models.FieldCondition(key="source_id", match=models.MatchValue(value=source_id)),
            ])
        ),
        wait=True,
    )


def sync_chunks(db: Session, batch_size: int = 64) -> None:
    """Backfill SQL chunks into a new or partially populated Qdrant collection."""
    if not enabled():
        return
    total = db.scalar(select(func.count()).select_from(Chunk)) or 0
    if not total:
        return
    info = collection_info()
    if info.points_count == total:
        return
    log.info("Syncing %s SQL chunks to Qdrant (collection currently has %s points)", total, info.points_count)
    rows = db.scalars(select(Chunk).order_by(Chunk.id)).all()
    for offset in range(0, len(rows), batch_size):
        batch = rows[offset:offset + batch_size]
        upsert_chunks([
            {"id": c.id, "source_type": c.source_type, "source_id": c.source_id,
             "workspace_id": c.workspace_id, "title": c.title, "text": c.text}
            for c in batch
        ])


def search(query: str, workspace_id: int, limit: int = 5):
    if not _client().collection_exists(settings.qdrant_collection):
        return []
    vector = next(_embedding_model().embed([query])).tolist()
    visibility = models.Filter(should=[
        models.IsNullCondition(is_null=models.PayloadField(key="workspace_id")),
        models.FieldCondition(key="workspace_id", match=models.MatchValue(value=workspace_id)),
    ])
    return _client().query_points(
        collection_name=settings.qdrant_collection, query=vector, query_filter=visibility,
        limit=limit, score_threshold=settings.min_score, with_payload=True,
    ).points
