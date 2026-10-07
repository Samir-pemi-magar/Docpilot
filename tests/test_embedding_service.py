from io import BytesIO
from uuid import uuid4

import pytest

from app.chunking.models import Chunk as ChunkData
from app.chunking.models import NormalizedElementType
from app.embeddings.models import EmbeddingResult
from app.models.organization import Organization
from app.services.chunk import create_chunks
from app.services.document import create_document
from app.services.embedding import create_embeddings, list_embeddings


@pytest.mark.asyncio
async def test_create_and_list_embeddings(
    db_session,
    test_user,
    test_storage,
):
    organization = Organization(
        name="Embedding Test Organization",
        slug="embedding-test-organization",
    )

    db_session.add(organization)
    await db_session.flush()

    version = await create_document(
        db=db_session,
        storage=test_storage,
        organization_id=organization.id,
        user_id=test_user.id,
        name="Embedding test document",
        original_filename="embedding-test.txt",
        content_type="text/plain",
        file=BytesIO(b"Hello embeddings"),
    )

    chunks = await create_chunks(
        db=db_session,
        document_version_id=version.id,
        chunks=[
            ChunkData(
                id="embedding-chunk-1",
                text="First chunk",
                element_type=NormalizedElementType.PARAGRAPH,
                source_element_indexes=[0],
                token_count=2,
            ),
            ChunkData(
                id="embedding-chunk-2",
                text="Second chunk",
                element_type=NormalizedElementType.PARAGRAPH,
                source_element_indexes=[1],
                token_count=2,
            ),
        ],
    )

    vector_one = [0.1] * 1024
    vector_two = [0.2] * 1024

    embeddings = await create_embeddings(
        db=db_session,
        chunk_embeddings=[
            (
                chunks[0].id,
                EmbeddingResult(
                    vector=vector_one,
                    model="BAAI/bge-m3",
                    dimension=1024,
                ),
            ),
            (
                chunks[1].id,
                EmbeddingResult(
                    vector=vector_two,
                    model="BAAI/bge-m3",
                    dimension=1024,
                ),
            ),
        ],
    )

    await db_session.commit()

    assert len(embeddings) == 2
    assert all(embedding.id is not None for embedding in embeddings)

    stored = await list_embeddings(
        db=db_session,
        chunk_id=chunks[0].id,
    )

    assert len(stored) == 1
    assert stored[0].chunk_id == chunks[0].id
    assert stored[0].model == "BAAI/bge-m3"
    assert stored[0].dimension == 1024
    assert len(stored[0].embedding) == 1024
    assert stored[0].embedding[0] == pytest.approx(0.1)


@pytest.mark.asyncio
async def test_list_embeddings_isolated_by_chunk(
    db_session,
    test_user,
    test_storage,
):
    organization = Organization(
        name="Embedding Isolation Organization",
        slug="embedding-isolation-organization",
    )

    db_session.add(organization)
    await db_session.flush()

    version = await create_document(
        db=db_session,
        storage=test_storage,
        organization_id=organization.id,
        user_id=test_user.id,
        name="Embedding isolation document",
        original_filename="embedding-isolation.txt",
        content_type="text/plain",
        file=BytesIO(b"Embedding isolation"),
    )

    chunks = await create_chunks(
        db=db_session,
        document_version_id=version.id,
        chunks=[
            ChunkData(
                id="isolation-chunk-1",
                text="First chunk",
                element_type=NormalizedElementType.PARAGRAPH,
                source_element_indexes=[0],
                token_count=2,
            ),
            ChunkData(
                id="isolation-chunk-2",
                text="Second chunk",
                element_type=NormalizedElementType.PARAGRAPH,
                source_element_indexes=[1],
                token_count=2,
            ),
        ],
    )

    await create_embeddings(
        db=db_session,
        chunk_embeddings=[
            (
                chunks[0].id,
                EmbeddingResult(
                    vector=[0.1] * 1024,
                    model="BAAI/bge-m3",
                    dimension=1024,
                ),
            ),
            (
                chunks[1].id,
                EmbeddingResult(
                    vector=[0.2] * 1024,
                    model="BAAI/bge-m3",
                    dimension=1024,
                ),
            ),
        ],
    )

    await db_session.commit()

    first = await list_embeddings(
        db=db_session,
        chunk_id=chunks[0].id,
    )

    second = await list_embeddings(
        db=db_session,
        chunk_id=chunks[1].id,
    )

    assert len(first) == 1
    assert len(second) == 1

    assert first[0].chunk_id == chunks[0].id
    assert second[0].chunk_id == chunks[1].id

    assert first[0].embedding[0] == pytest.approx(0.1)
    assert second[0].embedding[0] == pytest.approx(0.2)


@pytest.mark.asyncio
async def test_create_embeddings_with_empty_input_returns_empty_list(
    db_session,
):
    result = await create_embeddings(
        db=db_session,
        chunk_embeddings=[],
    )

    assert result == []


@pytest.mark.asyncio
async def test_create_embeddings_rejects_missing_chunk(
    db_session,
):
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await create_embeddings(
            db=db_session,
            chunk_embeddings=[
                (
                    uuid4(),
                    EmbeddingResult(
                        vector=[0.1] * 1024,
                        model="BAAI/bge-m3",
                        dimension=1024,
                    ),
                )
            ],
        )

    await db_session.rollback()
