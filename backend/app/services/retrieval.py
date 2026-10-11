from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.models.chunk_embedding import ChunkEmbedding
from app.models.document import Document
from app.models.document_version import DocumentVersion


@dataclass(frozen=True)
class RetrievedChunk:
    """A chunk returned by vector similarity search."""

    chunk: Chunk
    distance: float
    model: str
    document_id: uuid.UUID | None = None
    document_name: str = "Document"


async def retrieve_chunks(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    query_vector: list[float],
    model: str,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Retrieve the most similar chunks belonging to an organization."""

    if not query_vector:
        raise ValueError("Query vector must not be empty.")

    if len(query_vector) != 1024:
        raise ValueError("Query vector must contain exactly 1024 dimensions.")

    if not model.strip():
        raise ValueError("Embedding model must not be empty.")

    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    if top_k > 100:
        raise ValueError("top_k must not exceed 100.")

    distance = ChunkEmbedding.embedding.cosine_distance(query_vector)

    statement = (
        select(
            Chunk,
            distance.label("distance"),
            ChunkEmbedding.model,
            Document.id,
            Document.name,
        )
        .join(
            ChunkEmbedding,
            ChunkEmbedding.chunk_id == Chunk.id,
        )
        .join(
            DocumentVersion,
            DocumentVersion.id == Chunk.document_version_id,
        )
        .join(
            Document,
            Document.id == DocumentVersion.document_id,
        )
        .where(
            Document.organization_id == organization_id,
            ChunkEmbedding.model == model,
        )
        .order_by(distance)
        .limit(top_k)
    )

    result = await db.execute(statement)

    return [
        RetrievedChunk(
            chunk=chunk,
            distance=float(distance_value),
            model=embedding_model,
            document_id=document_id,
            document_name=document_name,
        )
        for chunk, distance_value, embedding_model, document_id, document_name
        in result.all()
    ]
