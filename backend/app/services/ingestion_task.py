from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.embeddings.dependencies import get_default_embedding_provider
from app.models.document_version import DocumentVersion
from app.processing.factory import create_document_processor
from app.services.ingestion import ingest_document_version
from app.api.dependencies import get_storage

logger = logging.getLogger(__name__)


async def process_document_version_background(
    document_version_id: uuid.UUID,
) -> None:
    """Process an uploaded version using an independent database session."""

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DocumentVersion).where(
                DocumentVersion.id == document_version_id
            )
        )
        version = result.scalar_one_or_none()

        if version is None:
            logger.warning(
                "Document version %s no longer exists.",
                document_version_id,
            )
            return

        version.ingestion_status = "processing"
        await db.commit()

        try:
            await ingest_document_version(
                db=db,
                storage=get_storage(),
                document_version=version,
                processor=create_document_processor(),
                embedding_provider=get_default_embedding_provider(),
            )
        except Exception:
            await db.rollback()
            logger.exception(
                "Ingestion failed for document version %s.",
                document_version_id,
            )

            result = await db.execute(
                select(DocumentVersion).where(
                    DocumentVersion.id == document_version_id
                )
            )
            version = result.scalar_one_or_none()

            if version is not None:
                version.ingestion_status = "failed"
                await db.commit()
