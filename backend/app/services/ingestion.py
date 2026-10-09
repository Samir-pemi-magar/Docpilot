from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.embeddings.base import EmbeddingProvider
from app.models.chunk import Chunk
from app.models.document_version import DocumentVersion
from app.processing.processor import DocumentProcessor
from app.services.chunk import create_chunks
from app.services.document import open_document
from app.services.embedding import create_embeddings
from app.storage.base import StorageService


@dataclass(frozen=True)
class IngestionResult:
    """Result of processing and embedding one document version."""

    document_version: DocumentVersion
    chunks: list[Chunk]


async def ingest_document_version(
    db: AsyncSession,
    storage: StorageService,
    document_version: DocumentVersion,
    processor: DocumentProcessor,
    embedding_provider: EmbeddingProvider,
) -> IngestionResult:
    """Process, chunk, and embed a document version."""

    with open_document(
        storage=storage,
        version=document_version,
    ) as file:
        processing_result = await run_in_threadpool(
            processor.process,
            filename=document_version.original_filename,
            file=file,
        )

    db_chunks = await create_chunks(
        db=db,
        document_version_id=document_version.id,
        chunks=processing_result.chunks,
    )

    embedding_batch = await run_in_threadpool(
        embedding_provider.embed_documents,
        [chunk.text for chunk in processing_result.chunks],
    )

    if len(embedding_batch.embeddings) != len(db_chunks):
        raise RuntimeError(
            "Embedding provider returned a different number of embeddings "
            "than the number of chunks."
        )

    await create_embeddings(
        db=db,
        chunk_embeddings=[
            (db_chunk.id, embedding)
            for db_chunk, embedding in zip(
                db_chunks,
                embedding_batch.embeddings,
                strict=True,
            )
        ],
    )

    document_version.ingestion_status = "completed"
    await db.commit()

    return IngestionResult(
        document_version=document_version,
        chunks=db_chunks,
    )
