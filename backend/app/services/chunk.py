from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chunking.models import Chunk as ChunkData
from app.models.chunk import Chunk


async def create_chunks(
    db: AsyncSession,
    document_version_id: uuid.UUID,
    chunks: Sequence[ChunkData],
) -> list[Chunk]:
    """Persist processed chunks for a document version."""

    db_chunks = [
        Chunk(
            document_version_id=document_version_id,
            chunk_index=index,
            text=chunk.text,
            element_type=chunk.element_type.value,
            source_element_indexes=chunk.source_element_indexes,
            metadata_=chunk.metadata,
            character_count=chunk.character_count,
            token_count=chunk.token_count,
        )
        for index, chunk in enumerate(chunks)
    ]

    db.add_all(db_chunks)

    await db.flush()

    return db_chunks


async def list_chunks(
    db: AsyncSession,
    document_version_id: uuid.UUID,
) -> list[Chunk]:
    """List all chunks belonging to a document version."""

    result = await db.execute(
        select(Chunk)
        .where(Chunk.document_version_id == document_version_id)
        .order_by(Chunk.chunk_index)
    )

    return list(result.scalars().all())
