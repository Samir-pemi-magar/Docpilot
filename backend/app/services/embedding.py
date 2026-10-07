from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.embeddings.models import EmbeddingResult
from app.models.chunk_embedding import ChunkEmbedding


async def create_embeddings(
    db: AsyncSession,
    chunk_embeddings: Sequence[tuple[uuid.UUID, EmbeddingResult]],
) -> list[ChunkEmbedding]:
    """Persist embeddings for chunks."""

    db_embeddings = [
        ChunkEmbedding(
            chunk_id=chunk_id,
            model=result.model,
            dimension=result.dimension,
            embedding=result.vector,
        )
        for chunk_id, result in chunk_embeddings
    ]

    db.add_all(db_embeddings)

    await db.flush()

    return db_embeddings


async def list_embeddings(
    db: AsyncSession,
    chunk_id: uuid.UUID,
) -> list[ChunkEmbedding]:
    """List all embeddings belonging to a chunk."""

    result = await db.execute(
        select(ChunkEmbedding)
        .where(ChunkEmbedding.chunk_id == chunk_id)
        .order_by(ChunkEmbedding.model)
    )

    return list(result.scalars().all())
