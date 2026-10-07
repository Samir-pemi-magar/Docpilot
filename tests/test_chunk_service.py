from io import BytesIO

import pytest

from app.chunking.models import Chunk as ChunkData
from app.chunking.models import NormalizedElementType
from app.models.organization import Organization
from app.services.chunk import create_chunks, list_chunks
from app.services.document import create_document


@pytest.mark.asyncio
async def test_create_and_list_chunks(
    db_session,
    test_user,
    test_storage,
):
    organization = Organization(
        name="Chunk Test Organization",
        slug="chunk-test-organization",
    )

    db_session.add(organization)
    await db_session.flush()

    version = await create_document(
        db=db_session,
        storage=test_storage,
        organization_id=organization.id,
        user_id=test_user.id,
        name="Chunk test document",
        original_filename="chunk-test.txt",
        content_type="text/plain",
        file=BytesIO(b"Hello chunking"),
    )

    chunks = [
        ChunkData(
            id="chunk-1",
            text="First chunk",
            element_type=NormalizedElementType.PARAGRAPH,
            source_element_indexes=[0],
            token_count=2,
        ),
        ChunkData(
            id="chunk-2",
            text="Second chunk",
            element_type=NormalizedElementType.PARAGRAPH,
            source_element_indexes=[1],
            token_count=2,
        ),
    ]

    db_chunks = await create_chunks(
        db=db_session,
        document_version_id=version.id,
        chunks=chunks,
    )

    await db_session.commit()

    assert len(db_chunks) == 2
    assert all(chunk.id is not None for chunk in db_chunks)

    stored = await list_chunks(
        db=db_session,
        document_version_id=version.id,
    )

    assert len(stored) == 2
    assert [chunk.chunk_index for chunk in stored] == [0, 1]
    assert [chunk.text for chunk in stored] == [
        "First chunk",
        "Second chunk",
    ]
    assert [chunk.element_type for chunk in stored] == [
        "paragraph",
        "paragraph",
    ]
    assert [chunk.source_element_indexes for chunk in stored] == [
        [0],
        [1],
    ]
    assert [chunk.character_count for chunk in stored] == [
        len("First chunk"),
        len("Second chunk"),
    ]
    assert [chunk.token_count for chunk in stored] == [2, 2]


@pytest.mark.asyncio
async def test_list_chunks_is_isolated_by_document_version(
    db_session,
    test_user,
    test_storage,
):
    organization = Organization(
        name="Chunk Isolation Organization",
        slug="chunk-isolation-organization",
    )

    db_session.add(organization)
    await db_session.flush()

    version_one = await create_document(
        db=db_session,
        storage=test_storage,
        organization_id=organization.id,
        user_id=test_user.id,
        name="Document one",
        original_filename="one.txt",
        content_type="text/plain",
        file=BytesIO(b"Document one"),
    )

    version_two = await create_document(
        db=db_session,
        storage=test_storage,
        organization_id=organization.id,
        user_id=test_user.id,
        name="Document two",
        original_filename="two.txt",
        content_type="text/plain",
        file=BytesIO(b"Document two"),
    )

    await create_chunks(
        db=db_session,
        document_version_id=version_one.id,
        chunks=[
            ChunkData(
                id="chunk-one",
                text="Only belongs to version one",
                element_type=NormalizedElementType.PARAGRAPH,
                source_element_indexes=[0],
                token_count=5,
            )
        ],
    )

    await create_chunks(
        db=db_session,
        document_version_id=version_two.id,
        chunks=[
            ChunkData(
                id="chunk-two",
                text="Only belongs to version two",
                element_type=NormalizedElementType.PARAGRAPH,
                source_element_indexes=[0],
                token_count=5,
            )
        ],
    )

    await db_session.commit()

    version_one_chunks = await list_chunks(
        db=db_session,
        document_version_id=version_one.id,
    )

    version_two_chunks = await list_chunks(
        db=db_session,
        document_version_id=version_two.id,
    )

    assert len(version_one_chunks) == 1
    assert len(version_two_chunks) == 1

    assert version_one_chunks[0].text == "Only belongs to version one"
    assert version_two_chunks[0].text == "Only belongs to version two"


@pytest.mark.asyncio
async def test_create_chunks_with_empty_input_returns_empty_list(
    db_session,
):
    result = await create_chunks(
        db=db_session,
        document_version_id=__import__("uuid").uuid4(),
        chunks=[],
    )

    assert result == []


@pytest.mark.asyncio
async def test_create_chunks_rejects_missing_document_version(
    db_session,
):
    from uuid import uuid4

    from sqlalchemy.exc import IntegrityError

    chunk = ChunkData(
        id="orphan-chunk",
        text="This should not be stored",
        element_type=NormalizedElementType.PARAGRAPH,
        source_element_indexes=[0],
        token_count=5,
    )

    with pytest.raises(IntegrityError):
        await create_chunks(
            db=db_session,
            document_version_id=uuid4(),
            chunks=[chunk],
        )

    await db_session.rollback()
