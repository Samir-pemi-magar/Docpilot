from app.chunking.models import Chunk, ChunkedDocument
from app.normalization.models import NormalizedElementType


def test_chunk_basic_properties() -> None:
    chunk = Chunk(
        id="document-1:chunk-0001",
        text="Applications open January 1.",
        element_type=NormalizedElementType.PARAGRAPH,
    )

    assert chunk.id == "document-1:chunk-0001"
    assert chunk.text == "Applications open January 1."
    assert chunk.element_type == NormalizedElementType.PARAGRAPH


def test_chunk_calculates_character_count() -> None:
    chunk = Chunk(
        id="document-1:chunk-0001",
        text="Hello world",
        element_type=NormalizedElementType.PARAGRAPH,
    )

    assert chunk.character_count == len("Hello world")


def test_chunk_stores_token_count() -> None:
    chunk = Chunk(
        id="document-1:chunk-0001",
        text="Hello world",
        element_type=NormalizedElementType.PARAGRAPH,
        token_count=2,
    )

    assert chunk.token_count == 2


def test_chunk_preserves_source_element_indexes() -> None:
    chunk = Chunk(
        id="document-1:chunk-0001",
        text="Applications open January 1.",
        element_type=NormalizedElementType.PARAGRAPH,
        source_element_indexes=[1, 2],
    )

    assert chunk.source_element_indexes == [1, 2]


def test_chunk_preserves_metadata() -> None:
    metadata = {
        "page_number": 3,
        "heading_path": ["Admissions", "Applications"],
    }

    chunk = Chunk(
        id="document-1:chunk-0001",
        text="Applications open January 1.",
        element_type=NormalizedElementType.PARAGRAPH,
        metadata=metadata,
    )

    assert chunk.metadata == metadata


def test_chunked_document_preserves_chunk_order() -> None:
    first = Chunk(
        id="document-1:chunk-0001",
        text="First chunk",
        element_type=NormalizedElementType.PARAGRAPH,
    )

    second = Chunk(
        id="document-1:chunk-0002",
        text="Second chunk",
        element_type=NormalizedElementType.PARAGRAPH,
    )

    document = ChunkedDocument(
        source_type="pdf",
        chunks=[first, second],
    )

    assert document.source_type == "pdf"
    assert document.chunks == [first, second]


def test_chunked_document_preserves_metadata() -> None:
    document = ChunkedDocument(
        source_type="xlsx",
        metadata={
            "filename": "admissions.xlsx",
        },
    )

    assert document.metadata["filename"] == "admissions.xlsx"
