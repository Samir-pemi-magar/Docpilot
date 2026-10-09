from __future__ import annotations

import io
import os

import pytest

from app.embeddings.local_bge_m3 import LocalBGEEmbeddingProvider
from app.processing.factory import create_document_processor
from app.services.document import create_document
from app.services.embedding import list_embeddings
from app.services.ingestion import ingest_document_version
from app.services.retrieval import retrieve_chunks
from app.storage.local import LocalStorage


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_REAL_BGE_TEST") != "1",
    reason="Set RUN_REAL_BGE_TEST=1 to run the real-model integration test.",
)


@pytest.mark.asyncio
async def test_real_bge_ingestion(db_session, test_user, tmp_path):
    from tests.test_ingestion import create_organization

    storage = LocalStorage(tmp_path / "real-bge-storage")

    organization = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Real BGE Test Organization",
        slug="real-bge-test-organization",
    )

    version = await create_document(
        db=db_session,
        storage=storage,
        organization_id=organization.id,
        user_id=test_user.id,
        name="Real BGE integration test",
        original_filename="real-bge-test.txt",
        content_type="text/plain",
        file=io.BytesIO(
            b"DocPilot stores organization documents and retrieves "
            b"relevant information using semantic embeddings."
        ),
    )

    provider = LocalBGEEmbeddingProvider(device="cpu", use_fp16=False)

    result = await ingest_document_version(
        db=db_session,
        storage=storage,
        document_version=version,
        processor=create_document_processor(),
        embedding_provider=provider,
    )

    assert result.document_version.ingestion_status == "completed"
    assert result.chunks

    for chunk in result.chunks:
        embeddings = await list_embeddings(db_session, chunk.id)

        assert len(embeddings) == 1
        assert embeddings[0].model == "BAAI/bge-m3"
        assert embeddings[0].dimension == 1024
        assert len(embeddings[0].embedding) == 1024
        assert any(float(value) != 0.0 for value in embeddings[0].embedding)

    query = provider.embed_query(
        "How does DocPilot retrieve relevant information from documents?"
    )

    retrieved = await retrieve_chunks(
        db_session,
        organization_id=organization.id,
        query_vector=query.vector,
        model=query.model,
        top_k=5,
    )

    assert retrieved
    assert any(chunk.chunk.id == result.chunks[0].id for chunk in retrieved)
    assert all(item.model == "BAAI/bge-m3" for item in retrieved)

    print(
        f"\\nREAL BGE INGESTION + RETRIEVAL PASSED: "
        f"{len(result.chunks)} chunks ingested; "
        f"{len(retrieved)} chunks retrieved."
    )
