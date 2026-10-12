from __future__ import annotations

import uuid

import pytest

from app.models.chunk import Chunk
from app.models.chunk_embedding import ChunkEmbedding
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.membership import Membership
from app.models.organization import Organization
from app.services.retrieval import (
    retrieve_chunks,
    retrieve_hybrid_chunks,
    retrieve_keyword_chunks,
)


DIMENSION = 1024
MODEL = "fake-test-model"


def make_vector(first: float, second: float = 0.0) -> list[float]:
    """Create a deterministic 1024-dimensional vector."""
    return [first, second] + [0.0] * (DIMENSION - 2)


async def create_organization(
    db_session,
    owner_id,
    name: str,
    slug: str,
):
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


async def create_chunk_with_embedding(
    db_session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    text: str,
    chunk_index: int,
    vector: list[float],
    model: str = MODEL,
):
    document = Document(
        organization_id=organization_id,
        created_by_user_id=user_id,
        name=f"Test Document {uuid.uuid4()}",
    )

    db_session.add(document)
    await db_session.flush()

    version = DocumentVersion(
        document_id=document.id,
        uploaded_by_user_id=user_id,
        version_number=1,
        original_filename="test.txt",
        content_type="text/plain",
        size_bytes=len(text.encode()),
        storage_object_key=f"test/{uuid.uuid4()}.txt",
        sha256="a" * 64,
    )

    db_session.add(version)
    await db_session.flush()

    chunk = Chunk(
        document_version_id=version.id,
        chunk_index=chunk_index,
        text=text,
        element_type="paragraph",
        source_element_indexes=[],
        metadata_={},
        character_count=len(text),
        token_count=len(text.split()),
    )

    db_session.add(chunk)
    await db_session.flush()

    embedding = ChunkEmbedding(
        chunk_id=chunk.id,
        model=model,
        dimension=DIMENSION,
        embedding=vector,
    )

    db_session.add(embedding)
    await db_session.flush()

    return chunk


async def test_retrieve_chunks_returns_most_similar_first(
    db_session,
    test_user,
):
    organization = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Retrieval Test Organization",
        slug="retrieval-test-organization",
    )

    first = await create_chunk_with_embedding(
        db_session,
        organization_id=organization.id,
        user_id=test_user.id,
        text="First chunk",
        chunk_index=0,
        vector=make_vector(1.0),
    )

    second = await create_chunk_with_embedding(
        db_session,
        organization_id=organization.id,
        user_id=test_user.id,
        text="Second chunk",
        chunk_index=1,
        vector=make_vector(0.0, 1.0),
    )

    await db_session.commit()

    results = await retrieve_chunks(
        db_session,
        organization_id=organization.id,
        query_vector=make_vector(1.0),
        model=MODEL,
        top_k=2,
    )

    assert len(results) == 2
    assert results[0].chunk.id == first.id
    assert results[1].chunk.id == second.id
    assert results[0].distance < results[1].distance


async def test_retrieve_chunks_respects_top_k(
    db_session,
    test_user,
):
    organization = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Top K Test Organization",
        slug="top-k-test-organization",
    )

    vectors = [
        make_vector(1.0),
        make_vector(0.9, 0.1),
        make_vector(0.0, 1.0),
    ]

    for index, vector in enumerate(vectors):
        await create_chunk_with_embedding(
            db_session,
            organization_id=organization.id,
            user_id=test_user.id,
            text=f"Chunk {index}",
            chunk_index=index,
            vector=vector,
        )

    await db_session.commit()

    results = await retrieve_chunks(
        db_session,
        organization_id=organization.id,
        query_vector=make_vector(1.0),
        model=MODEL,
        top_k=2,
    )

    assert len(results) == 2


async def test_retrieve_chunks_is_organization_scoped(
    db_session,
    test_user,
):
    organization_a = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Organization A",
        slug=f"organization-a-{uuid.uuid4()}",
    )

    organization_b = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Organization B",
        slug=f"organization-b-{uuid.uuid4()}",
    )

    chunk_a = await create_chunk_with_embedding(
        db_session,
        organization_id=organization_a.id,
        user_id=test_user.id,
        text="Organization A chunk",
        chunk_index=0,
        vector=make_vector(1.0),
    )

    await create_chunk_with_embedding(
        db_session,
        organization_id=organization_b.id,
        user_id=test_user.id,
        text="Organization B chunk",
        chunk_index=0,
        vector=make_vector(1.0),
    )

    await db_session.commit()

    results = await retrieve_chunks(
        db_session,
        organization_id=organization_a.id,
        query_vector=make_vector(1.0),
        model=MODEL,
        top_k=10,
    )

    assert len(results) == 1
    assert results[0].chunk.id == chunk_a.id


async def test_retrieve_chunks_filters_by_model(
    db_session,
    test_user,
):
    organization = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Model Filter Organization",
        slug="model-filter-organization",
    )

    matching = await create_chunk_with_embedding(
        db_session,
        organization_id=organization.id,
        user_id=test_user.id,
        text="Matching model",
        chunk_index=0,
        vector=make_vector(1.0),
        model=MODEL,
    )

    await create_chunk_with_embedding(
        db_session,
        organization_id=organization.id,
        user_id=test_user.id,
        text="Different model",
        chunk_index=1,
        vector=make_vector(1.0),
        model="another-model",
    )

    await db_session.commit()

    results = await retrieve_chunks(
        db_session,
        organization_id=organization.id,
        query_vector=make_vector(1.0),
        model=MODEL,
        top_k=10,
    )

    assert len(results) == 1
    assert results[0].chunk.id == matching.id
    assert results[0].model == MODEL


async def test_retrieve_chunks_validates_query_vector(
    db_session,
    test_user,
):
    organization = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Validation Organization",
        slug="validation-organization",
    )

    with pytest.raises(ValueError, match="1024"):
        await retrieve_chunks(
            db_session,
            organization_id=organization.id,
            query_vector=[1.0],
            model=MODEL,
        )


async def test_retrieve_chunks_validates_top_k(
    db_session,
    test_user,
):
    organization = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Top K Validation Organization",
        slug="top-k-validation-organization",
    )

    with pytest.raises(ValueError, match="at least 1"):
        await retrieve_chunks(
            db_session,
            organization_id=organization.id,
            query_vector=make_vector(1.0),
            model=MODEL,
            top_k=0,
        )

    with pytest.raises(ValueError, match="100"):
        await retrieve_chunks(
            db_session,
            organization_id=organization.id,
            query_vector=make_vector(1.0),
            model=MODEL,
            top_k=101,
        )



async def test_keyword_retrieval_finds_exact_extension(
    db_session,
    test_user,
):
    organization = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Keyword Retrieval Organization",
        slug=f"keyword-retrieval-{uuid.uuid4()}",
    )

    matching = await create_chunk_with_embedding(
        db_session,
        organization_id=organization.id,
        user_id=test_user.id,
        text=(
            "Worksheet: Contacts\\n"
            "Name: International Office\\n"
            "Extension: 7319\\n"
            "Email: international@example.com"
        ),
        chunk_index=0,
        vector=make_vector(0.0, 1.0),
    )

    await create_chunk_with_embedding(
        db_session,
        organization_id=organization.id,
        user_id=test_user.id,
        text="Worksheet: Meal Plans\\nStandard plan: $731",
        chunk_index=1,
        vector=make_vector(1.0, 0.0),
    )

    await db_session.commit()

    results = await retrieve_keyword_chunks(
        db_session,
        organization_id=organization.id,
        query="7319",
        top_k=5,
    )

    assert results
    assert results[0].chunk.id == matching.id
    assert "Extension: 7319" in results[0].chunk.text
    assert results[0].distance is None
    assert results[0].model is None


async def test_keyword_retrieval_is_organization_scoped(
    db_session,
    test_user,
):
    organization_a = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Keyword Organization A",
        slug=f"keyword-a-{uuid.uuid4()}",
    )

    organization_b = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Keyword Organization B",
        slug=f"keyword-b-{uuid.uuid4()}",
    )

    await create_chunk_with_embedding(
        db_session,
        organization_id=organization_a.id,
        user_id=test_user.id,
        text="General information about student services.",
        chunk_index=0,
        vector=make_vector(1.0),
    )

    matching_b = await create_chunk_with_embedding(
        db_session,
        organization_id=organization_b.id,
        user_id=test_user.id,
        text="Scholarship deadline is January 15.",
        chunk_index=0,
        vector=make_vector(1.0),
    )

    await db_session.commit()

    results = await retrieve_keyword_chunks(
        db_session,
        organization_id=organization_a.id,
        query="scholarship deadline January 15",
        top_k=5,
    )

    assert all(item.chunk.id != matching_b.id for item in results)
    assert results == []



async def test_hybrid_retrieval_promotes_keyword_relevant_chunk(
    db_session,
    test_user,
):
    organization = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Hybrid Retrieval Organization",
        slug=f"hybrid-retrieval-{uuid.uuid4()}",
    )

    unrelated = await create_chunk_with_embedding(
        db_session,
        organization_id=organization.id,
        user_id=test_user.id,
        text="General information about student services.",
        chunk_index=0,
        vector=make_vector(1.0),
    )

    relevant = await create_chunk_with_embedding(
        db_session,
        organization_id=organization.id,
        user_id=test_user.id,
        text="Scholarship deadline is January 15.",
        chunk_index=1,
        vector=make_vector(0.0, 1.0),
    )

    await db_session.commit()

    # Vector search alone prefers the unrelated chunk.
    vector_results = await retrieve_chunks(
        db_session,
        organization_id=organization.id,
        query_vector=make_vector(1.0),
        model=MODEL,
        top_k=2,
    )
    assert vector_results[0].chunk.id == unrelated.id

    results = await retrieve_hybrid_chunks(
        db_session,
        organization_id=organization.id,
        query="scholarship deadline January 15",
        query_vector=make_vector(1.0),
        model=MODEL,
        top_k=2,
    )

    assert results
    assert results[0].chunk.id == relevant.id
    assert results[0].distance is None or results[0].distance >= 0.0
    assert any(item.chunk.id == unrelated.id for item in results)


async def test_hybrid_retrieval_prefers_current_policy_unless_history_requested(
    db_session,
    test_user,
):
    organization = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Policy Ranking Organization",
        slug=f"policy-ranking-{uuid.uuid4()}",
    )

    current = await create_chunk_with_embedding(
        db_session,
        organization_id=organization.id,
        user_id=test_user.id,
        text=(
            "Regular Decision deadline for international undergraduate "
            "applicants is 2027-12-01 23:59 NST."
        ),
        chunk_index=0,
        vector=make_vector(1.0),
    )
    current.metadata_ = {
        "table_title": "3.1 Application deadlines",
        "page_number": 2,
    }

    historical = await create_chunk_with_embedding(
        db_session,
        organization_id=organization.id,
        user_id=test_user.id,
        text=(
            "Historical Regular Decision deadline for international "
            "undergraduate applicants was 2026-11-15 23:59 NST."
        ),
        chunk_index=1,
        vector=make_vector(0.0, 1.0),
    )
    historical.metadata_ = {
        "table_title": (
            "9. Historical rules (AH-2026.3) - "
            "SUPERSEDED, FOR REFERENCE ONLY"
        ),
        "page_number": 6,
    }

    await db_session.commit()

    normal_results = await retrieve_hybrid_chunks(
        db_session,
        organization_id=organization.id,
        query="Regular Decision deadline for international undergraduate applicants",
        query_vector=make_vector(1.0),
        model=MODEL,
        top_k=2,
    )

    assert normal_results[0].chunk.id == current.id

    historical_results = await retrieve_hybrid_chunks(
        db_session,
        organization_id=organization.id,
        query="What was the historical Regular Decision deadline for international undergraduate applicants?",
        query_vector=make_vector(1.0),
        model=MODEL,
        top_k=2,
    )

    assert historical_results[0].chunk.id == historical.id


async def test_hybrid_retrieval_prioritizes_refund_policy_title(
    db_session,
    test_user,
    monkeypatch,
):
    from app.services import retrieval

    organization = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Refund Policy Ranking Organization",
        slug=f"refund-policy-ranking-{uuid.uuid4()}",
    )

    budget = await create_chunk_with_embedding(
        db_session,
        organization_id=organization.id,
        user_id=test_user.id,
        text="Operating budget: tuition revenue and annual expenses.",
        chunk_index=0,
        vector=make_vector(1.0),
    )
    budget.element_type = "table"
    budget.metadata_ = {"table_title": "Annual Budget and Expenses"}

    admissions = await create_chunk_with_embedding(
        db_session,
        organization_id=organization.id,
        user_id=test_user.id,
        text="Admissions table: application and enrollment requirements.",
        chunk_index=1,
        vector=make_vector(0.0, 1.0),
    )
    admissions.element_type = "table"
    admissions.metadata_ = {"table_title": "Admissions Requirements"}

    refund = await create_chunk_with_embedding(
        db_session,
        organization_id=organization.id,
        user_id=test_user.id,
        text="Refund policy: eligible students receive a refund within 7 days.",
        chunk_index=2,
        vector=make_vector(0.0, 0.0),
    )
    refund.element_type = "table"
    refund.metadata_ = {"table_title": "Refund Policy"}

    await db_session.commit()

    async def fake_vector_results(*args, **kwargs):
        return [
            retrieval.RetrievedChunk(budget, 0.0, MODEL),
            retrieval.RetrievedChunk(admissions, 0.2, MODEL),
            retrieval.RetrievedChunk(refund, 0.4, MODEL),
        ]

    async def fake_keyword_results(*args, **kwargs):
        return [
            retrieval.RetrievedChunk(admissions, None, None),
            retrieval.RetrievedChunk(budget, None, None),
            retrieval.RetrievedChunk(refund, None, None),
        ]

    monkeypatch.setattr(retrieval, "retrieve_chunks", fake_vector_results)
    monkeypatch.setattr(
        retrieval,
        "retrieve_keyword_chunks",
        fake_keyword_results,
    )

    results = await retrieve_hybrid_chunks(
        db_session,
        organization_id=organization.id,
        query="When can I get my money back?",
        query_vector=make_vector(1.0),
        model=MODEL,
        top_k=3,
    )

    assert results[0].chunk.id == refund.id


async def test_hybrid_retrieval_applies_stronger_deadline_title_boost(
    db_session,
    test_user,
    monkeypatch,
):
    from app.services import retrieval

    organization = await create_organization(
        db_session=db_session,
        owner_id=test_user.id,
        name="Deadline Title Boost Organization",
        slug=f"deadline-title-boost-{uuid.uuid4()}",
    )

    matching = await create_chunk_with_embedding(
        db_session,
        organization_id=organization.id,
        user_id=test_user.id,
        text="The application closes on the stated date.",
        chunk_index=0,
        vector=make_vector(1.0),
    )
    matching.element_type = "table"
    matching.metadata_ = {"table_title": "Application Deadlines"}

    other = await create_chunk_with_embedding(
        db_session,
        organization_id=organization.id,
        user_id=test_user.id,
        text="The application closes on the stated date.",
        chunk_index=1,
        vector=make_vector(1.0),
    )
    other.element_type = "table"
    other.metadata_ = {"table_title": "Application Requirements"}

    await db_session.commit()

    async def fake_vector_results(*args, **kwargs):
        return [
            retrieval.RetrievedChunk(other, 0.0, MODEL),
            retrieval.RetrievedChunk(matching, 0.0, MODEL),
        ]

    async def fake_keyword_results(*args, **kwargs):
        return [
            retrieval.RetrievedChunk(other, None, MODEL),
            retrieval.RetrievedChunk(matching, None, MODEL),
        ]

    monkeypatch.setattr(retrieval, "retrieve_chunks", fake_vector_results)
    monkeypatch.setattr(
        retrieval,
        "retrieve_keyword_chunks",
        fake_keyword_results,
    )

    results = await retrieve_hybrid_chunks(
        db_session,
        organization_id=organization.id,
        query="application deadlines",
        query_vector=make_vector(1.0),
        model=MODEL,
        top_k=2,
    )

    assert len(results) == 2
    assert results[0].chunk.id == matching.id
    assert results[1].chunk.id == other.id
