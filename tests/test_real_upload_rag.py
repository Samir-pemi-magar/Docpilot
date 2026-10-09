from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.api.dependencies import get_document_ingestion_task
from app.embeddings.dependencies import get_embedding_provider
from app.embeddings.local_bge_m3 import LocalBGEEmbeddingProvider
from app.main import app
from app.models.chunk import Chunk
from app.models.document_version import DocumentVersion
from app.processing.factory import create_document_processor
from app.services.embedding import list_embeddings
from app.services.ingestion import ingest_document_version


pytestmark = pytest.mark.skipif(
    __import__("os").environ.get("RUN_REAL_UPLOAD_RAG") != "1",
    reason="Set RUN_REAL_UPLOAD_RAG=1 to run the real upload RAG test.",
)


@pytest.mark.asyncio
async def test_real_upload_background_ingestion_and_chat(
    client,
    db_session,
    test_user,
    test_storage,
):
    from tests.test_ingestion import create_organization

    organization = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Real Upload RAG Test",
        slug=f"real-upload-rag-{uuid.uuid4().hex[:12]}",
    )

    print("\nLoading real BGE-M3 embedding model on CPU...")
    provider = LocalBGEEmbeddingProvider(
        device="cpu",
        use_fp16=False,
    )

    # This adapter is invoked by FastAPI's actual BackgroundTasks mechanism.
    # It uses the test's isolated session and temporary storage.
    async def process_uploaded_version(version_id: uuid.UUID) -> None:
        result = await db_session.execute(
            select(DocumentVersion).where(
                DocumentVersion.id == version_id
            )
        )
        version = result.scalar_one_or_none()

        assert version is not None, (
            f"Uploaded document version {version_id} was not found."
        )

        await ingest_document_version(
            db=db_session,
            storage=test_storage,
            document_version=version,
            processor=create_document_processor(),
            embedding_provider=provider,
        )

    # Override the background task and chat embedding provider for this test.
    app.dependency_overrides[get_document_ingestion_task] = (
        lambda: process_uploaded_version
    )
    app.dependency_overrides[get_embedding_provider] = lambda: provider

    try:
        login_response = await client.post(
            "/auth/login",
            json={
                "email": test_user.email,
                "password": "TestPassword123!",
            },
        )
        assert login_response.status_code == 200, login_response.text

        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        document_text = (
            "DocPilot real upload workflow reference. "
            "The confidential test retrieval code is MAPLE-8426. "
            "The responsible department is the Northern Archive Team. "
            "This text verifies HTTP upload, background ingestion, "
            "embedding persistence, retrieval, and grounded answers."
        )

        # Upload through the real HTTP endpoint.
        upload_response = await client.post(
            f"/organizations/{organization.id}/documents",
            data={"name": "Real Upload RAG Verification"},
            files={
                "file": (
                    "real-upload-rag.txt",
                    document_text.encode("utf-8"),
                    "text/plain",
                )
            },
            headers=headers,
        )

        assert upload_response.status_code == 201, upload_response.text
        uploaded = upload_response.json()

        document_id = uuid.UUID(uploaded["id"])
        version_id = uuid.UUID(uploaded["version_id"])

        assert uploaded["version_number"] == 1
        assert uploaded["original_filename"] == "real-upload-rag.txt"
        assert uploaded["size_bytes"] == len(document_text.encode("utf-8"))

        print("\nHTTP upload succeeded.")
        print(f"Document ID: {document_id}")
        print(f"Version ID: {version_id}")
        print(f"Status in initial upload response: {uploaded['ingestion_status']}")

        # ASGITransport waits for the response's background tasks to finish.
        # Verify the persisted status through the actual document API.
        version_response = await client.get(
            f"/organizations/{organization.id}/documents/"
            f"{document_id}/versions/1",
            headers=headers,
        )

        assert version_response.status_code == 200, version_response.text
        version_data = version_response.json()

        assert version_data["id"] == str(version_id)
        assert version_data["ingestion_status"] == "completed", (
            f"Ingestion did not complete: {version_data}"
        )

        # Verify chunks and real embeddings were persisted.
        chunk_result = await db_session.execute(
            select(Chunk).where(
                Chunk.document_version_id == version_id
            )
        )
        chunks = list(chunk_result.scalars().all())

        assert chunks, "Ingestion produced no persisted chunks."

        for chunk in chunks:
            assert chunk.text.strip()
            assert chunk.character_count > 0
            assert chunk.token_count > 0

            embeddings = await list_embeddings(
                db=db_session,
                chunk_id=chunk.id,
            )

            assert embeddings, f"Chunk {chunk.id} has no embeddings."
            assert any(
                embedding.model == "BAAI/bge-m3"
                and embedding.dimension == 1024
                and len(embedding.embedding) == 1024
                for embedding in embeddings
            ), f"Chunk {chunk.id} has no valid BGE-M3 embedding."

        print(f"Persisted chunks: {len(chunks)}")
        print("Verified BGE-M3 embeddings: 1024 dimensions")

        # Ask a question whose answer comes from the uploaded document.
        question = "What is the confidential test retrieval code?"

        chat_response = await client.post(
            f"/organizations/{organization.id}/chat",
            json={"query": question, "top_k": 5},
            headers=headers,
        )

        assert chat_response.status_code == 200, chat_response.text

        answer_data = chat_response.json()
        assert answer_data["sources"], "Chat returned no retrieved sources."

        retrieved_text = "\n".join(
            source["text"] for source in answer_data["sources"]
        )

        assert "MAPLE-8426" in retrieved_text, (
            "The uploaded fact was not found in retrieved sources. "
            f"Sources: {retrieved_text!r}"
        )

        assert "MAPLE-8426" in answer_data["answer"], (
            "The generated answer did not contain the uploaded fact. "
            f"Answer: {answer_data['answer']!r}"
        )

        print("\n=== REAL UPLOAD-TO-RAG TEST PASSED ===")
        print("HTTP upload: passed")
        print("Background ingestion scheduling: passed")
        print("Ingestion status: completed")
        print("Chunk and embedding persistence: passed")
        print("Semantic retrieval: passed")
        print(f"Question: {question}")
        print(f"Answer: {answer_data['answer']}")
        print("Verified fact: MAPLE-8426")
        print("LLM: local Qwen")

    finally:
        app.dependency_overrides.pop(
            get_document_ingestion_task,
            None,
        )
        app.dependency_overrides.pop(
            get_embedding_provider,
            None,
        )
