from __future__ import annotations

import io
import os
import uuid

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.embeddings.local_bge_m3 import LocalBGEEmbeddingProvider
from app.models.chunk import Chunk
from app.models.chunk_embedding import ChunkEmbedding
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.organization import Organization
from app.models.user import User
from app.services import ingestion_task
from app.storage.local import LocalStorage


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_REAL_WORKER_TEST") != "1",
    reason="Set RUN_REAL_WORKER_TEST=1 to run the real worker integration test.",
)


@pytest.mark.asyncio
async def test_real_worker_success_and_failure(test_engine, tmp_path, monkeypatch):
    # This session factory uses the isolated test database. Unlike the usual
    # db_session fixture, it allows us to commit rows visible to the worker.
    SessionFactory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    storage = LocalStorage(tmp_path / "worker-storage")
    provider = LocalBGEEmbeddingProvider(device="cpu", use_fp16=False)

    monkeypatch.setattr(ingestion_task, "get_storage", lambda: storage)
    monkeypatch.setattr(
        ingestion_task,
        "get_default_embedding_provider",
        lambda: provider,
    )

    unique = uuid.uuid4().hex
    user_id = None
    organization_id = None
    success_version_id = None
    failure_version_id = None

    async def create_test_version(
        db: AsyncSession,
        organization: Organization,
        user: User,
        *,
        filename: str,
        content: bytes,
    ) -> DocumentVersion:
        document = Document(
            organization_id=organization.id,
            created_by_user_id=user.id,
            name=filename,
        )
        db.add(document)
        await db.flush()

        storage_key = (
            f"organizations/{organization.id}/"
            f"documents/{document.id}/versions/1/original.txt"
        )
        storage.save(io.BytesIO(content), storage_key)

        version = DocumentVersion(
            document_id=document.id,
            uploaded_by_user_id=user.id,
            version_number=1,
            original_filename=filename,
            content_type="text/plain",
            size_bytes=len(content),
            storage_object_key=storage_key,
            sha256=__import__("hashlib").sha256(content).hexdigest(),
            ingestion_status="pending",
        )
        db.add(version)
        await db.flush()
        return version

    try:
        async with SessionFactory() as db:
            user = User(
                email=f"worker-test-{unique}@example.com",
                password_hash="unused-test-hash",
                full_name="Disposable Worker Test User",
                is_active=True,
            )
            organization = Organization(
                name="Disposable Worker Test Organization",
                slug=f"worker-test-{unique}",
            )
            db.add_all([user, organization])
            await db.flush()

            user_id = user.id
            organization_id = organization.id

            successful_version = await create_test_version(
                db,
                organization,
                user,
                filename="worker-success.txt",
                content=(
                    b"Production worker integration test. "
                    b"The unique verification phrase is MAPLE-WORKER-8426. "
                    b"This document verifies actual background ingestion."
                ),
            )

            failed_version = await create_test_version(
                db,
                organization,
                user,
                filename="worker-failure.txt",
                content=b"Disposable document for testing failure handling.",
            )

            success_version_id = successful_version.id
            failure_version_id = failed_version.id

            # Commit so the worker's independent session can see these rows.
            await db.commit()

        # Exercise the real worker and its independent AsyncSessionLocal.
        await ingestion_task.process_document_version_background(
            success_version_id
        )

        async with SessionFactory() as db:
            result = await db.execute(
                select(DocumentVersion.ingestion_status).where(
                    DocumentVersion.id == success_version_id
                )
            )
            assert result.scalar_one() == "completed"

            chunk_count_result = await db.execute(
                select(func.count())
                .select_from(Chunk)
                .where(Chunk.document_version_id == success_version_id)
            )
            chunk_count = chunk_count_result.scalar_one()
            assert chunk_count > 0

            embedding_count_result = await db.execute(
                select(func.count())
                .select_from(ChunkEmbedding)
                .join(Chunk, Chunk.id == ChunkEmbedding.chunk_id)
                .where(Chunk.document_version_id == success_version_id)
            )
            embedding_count = embedding_count_result.scalar_one()
            assert embedding_count == chunk_count

            embedding_result = await db.execute(
                select(ChunkEmbedding)
                .join(Chunk, Chunk.id == ChunkEmbedding.chunk_id)
                .where(Chunk.document_version_id == success_version_id)
                .limit(1)
            )
            embedding = embedding_result.scalar_one()
            assert embedding.model == "BAAI/bge-m3"
            assert embedding.dimension == 1024
            assert len(embedding.embedding) == 1024

        print("Production worker independent database session: passed")
        print("Worker ingestion and completed status: passed")
        print(
            f"Persisted chunks: {chunk_count}; "
            f"persisted embeddings: {embedding_count}"
        )
        print("BGE-M3 1024-dimensional embedding verification: passed")

        # Replace only the ingestion operation to exercise the worker's
        # exception-handling path. The worker itself remains unmodified.
        async def simulated_ingestion_failure(**kwargs):
            raise RuntimeError("Intentional test-only ingestion failure")

        monkeypatch.setattr(
            ingestion_task,
            "ingest_document_version",
            simulated_ingestion_failure,
        )

        await ingestion_task.process_document_version_background(
            failure_version_id
        )

        async with SessionFactory() as db:
            result = await db.execute(
                select(DocumentVersion.ingestion_status).where(
                    DocumentVersion.id == failure_version_id
                )
            )
            assert result.scalar_one() == "failed"

        print("Worker failure handling and failed status: passed")

    finally:
        # Remove only the disposable organization and user created here.
        # Organization deletion cascades through documents, versions,
        # chunks, and embeddings. The storage files live under tmp_path.
        async with SessionFactory() as db:
            if organization_id is not None:
                await db.execute(
                    delete(Organization).where(
                        Organization.id == organization_id
                    )
                )

            if user_id is not None:
                await db.execute(
                    delete(User).where(User.id == user_id)
                )

            await db.commit()
