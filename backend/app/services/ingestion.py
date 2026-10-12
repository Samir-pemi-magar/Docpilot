from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
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
    """Process and embed a version before atomically persisting its chunks.

    Expensive document processing and embedding inference happen before
    acquiring a database row lock. Before inserting anything, lock and
    revalidate the version so concurrent deletion cannot invalidate the
    chunk foreign keys during persistence.
    """

    with open_document(
        storage=storage,
        version=document_version,
    ) as file:
        processing_result = await run_in_threadpool(
            processor.process,
            filename=document_version.original_filename,
            file=file,
        )

    embedding_batch = await run_in_threadpool(
        embedding_provider.embed_documents,
        [chunk.text for chunk in processing_result.chunks],
    )

    if len(embedding_batch.embeddings) != len(processing_result.chunks):
        raise RuntimeError(
            "Embedding provider returned a different number of embeddings "
            "than the number of processed chunks."
        )

    # Lock the parent row only after the expensive work has finished.
    # If another transaction already deleted it, do not insert orphaned work.
    result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.id == document_version.id)
        .with_for_update()
    )
    locked_version = result.scalar_one_or_none()

    if locked_version is None:
        raise LookupError(
            f"Document version {document_version.id} was deleted "
            "before ingestion could persist its results."
        )

    try:
        # Replace the previous index only after processing and embedding
        # have succeeded. The parent row lock serializes ingestion attempts
        # for this version, and the transaction keeps replacement atomic.
        await db.execute(
            delete(Chunk)
            .where(Chunk.document_version_id == locked_version.id)
            .execution_options(synchronize_session=False)
        )

        db_chunks = await create_chunks(
            db=db,
            document_version_id=locked_version.id,
            chunks=processing_result.chunks,
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

        locked_version.ingestion_status = "completed"
        await db.commit()

    except Exception:
        # A failed replacement must not leave the previous index deleted.
        await db.rollback()
        raise

    return IngestionResult(
        document_version=locked_version,
        chunks=db_chunks,
    )
