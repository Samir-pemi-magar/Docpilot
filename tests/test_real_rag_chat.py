from __future__ import annotations

import io
import os
import uuid

import pytest

from app.api.routes.chat import get_llm_client
from app.embeddings.dependencies import get_embedding_provider
from app.embeddings.local_bge_m3 import LocalBGEEmbeddingProvider
from app.main import app
from app.processing.factory import create_document_processor
from app.services.document import create_document
from app.services.ingestion import ingest_document_version
from app.storage.local import LocalStorage


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_REAL_RAG_CHAT") != "1",
    reason="Set RUN_REAL_RAG_CHAT=1 to run the real RAG integration test.",
)


@pytest.mark.asyncio
async def test_real_document_ingestion_and_chat(
    client,
    db_session,
    test_user,
    test_storage,
):
    from tests.test_ingestion import create_organization

    # Use a unique organization to avoid slug collisions.
    organization = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Real RAG Integration Test",
        slug=f"real-rag-{uuid.uuid4().hex[:12]}",
    )

    # This unique fact gives us a concrete way to verify retrieval
    # and answer grounding.
    document_text = (
        "DocPilot integration test reference. "
        "The internal project code for this test is ORBIT-7319. "
        "The support department is called the Cedar Operations Team. "
        "This document is used to verify real document ingestion, "
        "semantic retrieval, and grounded question answering."
    )

    version = await create_document(
        db=db_session,
        storage=test_storage,
        organization_id=organization.id,
        user_id=test_user.id,
        name="Real RAG verification document",
        original_filename="real-rag-verification.txt",
        content_type="text/plain",
        file=io.BytesIO(document_text.encode("utf-8")),
    )

    print("\nLoading real BGE-M3 embedding model on CPU...")
    provider = LocalBGEEmbeddingProvider(
        device="cpu",
        use_fp16=False,
    )

    # Run the actual document processing, chunking, and embedding pipeline.
    ingestion = await ingest_document_version(
        db=db_session,
        storage=test_storage,
        document_version=version,
        processor=create_document_processor(),
        embedding_provider=provider,
    )

    assert ingestion.document_version.ingestion_status == "completed"
    assert ingestion.chunks, "Ingestion produced no chunks."

    # Make the chat route use the same real model that created the
    # stored document embeddings.
    app.dependency_overrides[get_embedding_provider] = lambda: provider

    try:
        # Authenticate through the actual login endpoint.
        login_response = await client.post(
            "/auth/login",
            json={
                "email": test_user.email,
                "password": "TestPassword123!",
            },
        )
        assert login_response.status_code == 200, login_response.text

        token = login_response.json()["access_token"]

        # Ask a question that requires retrieving the unique document fact.
        question = "What is the internal project code for this test?"

        response = await client.post(
            f"/organizations/{organization.id}/chat",
            json={"query": question, "top_k": 5},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200, response.text

        data = response.json()
        assert data["answer"].strip(), "The LLM returned an empty answer."
        assert data["sources"], "Chat returned no retrieved source chunks."

        retrieved_text = "\n".join(
            source["text"] for source in data["sources"]
        )

        # Verify that retrieval supplied the document's actual unique fact.
        assert "ORBIT-7319" in retrieved_text, (
            "The expected document fact was not present in retrieved sources. "
            f"Retrieved text: {retrieved_text!r}"
        )

        # Verify that the generated answer is grounded in that fact.
        assert "ORBIT-7319" in data["answer"], (
            "The answer did not include the expected project code. "
            f"Answer: {data['answer']!r}"
        )

        print("\n=== REAL RAG INTEGRATION PASSED ===")
        print(f"Document version: {version.id}")
        print(f"Ingested chunks: {len(ingestion.chunks)}")
        print(f"Retrieved sources: {len(data['sources'])}")
        print(f"Question: {question}")
        print(f"Answer: {data['answer']}")
        print("Verified fact: ORBIT-7319")
        print("Pipeline: real BGE-M3 -> PostgreSQL retrieval -> local Qwen")

    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
