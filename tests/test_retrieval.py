from __future__ import annotations

import uuid

import pytest

from app.models.chunk import Chunk
from app.models.chunk_embedding import ChunkEmbedding
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.membership import Membership
from app.models.organization import Organization
from app.services.retrieval import retrieve_chunks


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
