from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.storage.base import StorageService


logger = logging.getLogger(__name__)


def calculate_file_metadata(file: BinaryIO) -> tuple[int, str]:
    """Calculate the file size and SHA-256 hash."""

    hasher = hashlib.sha256()
    size = 0

    while chunk := file.read(1024 * 1024):
        size += len(chunk)
        hasher.update(chunk)

    file.seek(0)

    return size, hasher.hexdigest()


def build_storage_object_key(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    version_number: int,
    original_filename: str,
) -> str:
    """Build the storage key for a document version."""

    suffix = Path(original_filename).suffix.lower()

    filename = f"original{suffix}" if suffix else "original"

    return (
        f"organizations/{organization_id}/"
        f"documents/{document_id}/"
        f"versions/{version_number}/"
        f"{filename}"
    )


async def create_document(
    db: AsyncSession,
    storage: StorageService,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    original_filename: str,
    content_type: str,
    file: BinaryIO,
) -> DocumentVersion:
    """Create a Document and its first version."""

    size_bytes, sha256 = calculate_file_metadata(file)

    document = Document(
        organization_id=organization_id,
        created_by_user_id=user_id,
        name=name,
    )

    db.add(document)

    await db.flush()

    version_number = 1

    storage_key = build_storage_object_key(
        organization_id=organization_id,
        document_id=document.id,
        version_number=version_number,
        original_filename=original_filename,
    )

    try:
        storage.save(file, storage_key)
    except Exception:
        await db.rollback()
        raise

    version = DocumentVersion(
        document_id=document.id,
        uploaded_by_user_id=user_id,
        version_number=version_number,
        original_filename=original_filename,
        content_type=content_type,
        size_bytes=size_bytes,
        storage_object_key=storage_key,
        sha256=sha256,
    )

    db.add(version)

    try:
        await db.commit()
    except Exception:
        await db.rollback()

        try:
            storage.delete(storage_key)
        except Exception:
            pass

        raise

    await db.refresh(version)

    return version


async def get_document(
    db: AsyncSession,
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
) -> Document | None:
    """Get a document belonging to an organization."""

    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
    )

    return result.scalar_one_or_none()


async def list_documents(
    db: AsyncSession,
    organization_id: uuid.UUID,
) -> list[Document]:
    """List all documents belonging to an organization."""

    result = await db.execute(
        select(Document)
        .where(Document.organization_id == organization_id)
        .order_by(Document.created_at.desc())
    )

    return list(result.scalars().all())


async def get_document_version(
    db: AsyncSession,
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    version_number: int,
) -> DocumentVersion | None:
    """Get a specific document version belonging to an organization."""

    result = await db.execute(
        select(DocumentVersion)
        .join(Document, Document.id == DocumentVersion.document_id)
        .where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.version_number == version_number,
            Document.organization_id == organization_id,
        )
    )

    return result.scalar_one_or_none()


def open_document(
    storage: StorageService,
    version: DocumentVersion,
) -> BinaryIO:
    """Open a stored document version for reading."""

    return storage.open(version.storage_object_key)


async def delete_document(
    db: AsyncSession,
    storage: StorageService,
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
) -> bool:
    """Delete a document and its stored files."""

    document = await get_document(
        db=db,
        organization_id=organization_id,
        document_id=document_id,
    )

    if document is None:
        return False

    versions_result = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document_id
        )
    )

    versions = list(versions_result.scalars().all())

    storage_keys = [
        version.storage_object_key
        for version in versions
    ]

    try:
        await db.delete(document)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    for storage_key in storage_keys:
        try:
            if storage.exists(storage_key):
                storage.delete(storage_key)
        except Exception:
            logger.exception(
                "Failed to delete storage object after document deletion: %s",
                storage_key,
            )

    return True
