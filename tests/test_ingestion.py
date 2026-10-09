from __future__ import annotations

import io

from app.embeddings.models import BatchEmbeddingResult, EmbeddingResult
from app.processing.factory import create_document_processor
from app.services.document import create_document
from app.services.ingestion import ingest_document_version
from app.storage.local import LocalStorage


class FakeEmbeddingProvider:
    """Small deterministic embedding provider for tests."""

    MODEL = "fake-test-model"
    DIMENSION = 1024

    def embed_query(self, text: str) -> EmbeddingResult:
        if not text.strip():
            raise ValueError("Cannot embed empty query text.")

        return EmbeddingResult(
            vector=[0.1] * self.DIMENSION,
            model=self.MODEL,
            dimension=self.DIMENSION,
        )

    def embed_documents(
        self,
        texts: list[str],
    ) -> BatchEmbeddingResult:
        return BatchEmbeddingResult(
            embeddings=[
                EmbeddingResult(
                    vector=[float(index + 1)] * self.DIMENSION,
                    model=self.MODEL,
                    dimension=self.DIMENSION,
                )
                for index, _ in enumerate(texts)
            ]
        )


async def create_organization(
    db_session,
    owner_id,
    name: str,
    slug: str,
):
    from app.models.membership import Membership
    from app.models.organization import Organization

    organization = Organization(
        name=name,
        slug=slug,
    )

    db_session.add(organization)
    await db_session.flush()

    membership = Membership(
        organization_id=organization.id,
        user_id=owner_id,
        role="owner",
    )

    db_session.add(membership)
    await db_session.flush()

    return organization


async def test_ingest_document_version(
    db_session,
    test_user,
    tmp_path,
):
    storage = LocalStorage(tmp_path / "storage")

    organization = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Ingestion Test Organization",
        slug="ingestion-test-organization",
    )

    version = await create_document(
        db=db_session,
        storage=storage,
        organization_id=organization.id,
        user_id=test_user.id,
        name="Ingestion test",
        original_filename="test.txt",
        content_type="text/plain",
        file=io.BytesIO(
            b"This is a document that will be processed and embedded."
        ),
    )

    processor = create_document_processor()
    embedding_provider = FakeEmbeddingProvider()

    result = await ingest_document_version(
        db=db_session,
        storage=storage,
        document_version=version,
        processor=processor,
        embedding_provider=embedding_provider,
    )

    assert result.document_version.id == version.id
    assert result.document_version.ingestion_status == "completed"
    assert len(result.chunks) > 0

    from app.services.embedding import list_embeddings

    for chunk in result.chunks:
        assert chunk.document_version_id == version.id
        assert chunk.text.strip()
        assert chunk.character_count > 0
        assert chunk.token_count > 0

        embeddings = await list_embeddings(
            db=db_session,
            chunk_id=chunk.id,
        )

        assert len(embeddings) == 1
        assert embeddings[0].model == "fake-test-model"
        assert embeddings[0].dimension == 1024
        assert len(embeddings[0].embedding) == 1024
