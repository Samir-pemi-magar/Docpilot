from app.chunking.config import ChunkingConfig
from app.chunking.structured import StructuredChunker
from app.chunking.tokenizer import SimpleTokenCounter
from app.normalization.models import (
    NormalizedDocument,
    NormalizedElement,
    NormalizedElementType,
)


def make_chunker(
    target_tokens: int = 5,
    max_tokens: int = 10,
    overlap_tokens: int = 0,
) -> StructuredChunker:
    return StructuredChunker(
        config=ChunkingConfig(
            target_tokens=target_tokens,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        ),
        token_counter=SimpleTokenCounter(),
    )


def test_structured_chunker_creates_chunk_from_table() -> None:
    document = NormalizedDocument(
        source_type="xlsx",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.TABLE,
                text=(
                    "Program | Duration | Fee\n"
                    "BSc CS | 4 years | $5000"
                ),
                metadata={
                    "sheet": "Programs",
                    "start_row": 1,
                    "end_row": 2,
                },
            ),
        ],
    )

    chunks = make_chunker().chunk(document)

    assert len(chunks) == 1
    assert chunks[0].element_type == NormalizedElementType.TABLE
    assert "Program | Duration | Fee" in chunks[0].text
    assert "BSc CS | 4 years | $5000" in chunks[0].text


def test_structured_chunker_preserves_source_indexes() -> None:
    document = NormalizedDocument(
        source_type="xlsx",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.TABLE,
                text="Program | Duration\nBSc CS | 4 years",
            ),
        ],
    )

    chunks = make_chunker().chunk(document)

    assert chunks[0].source_element_indexes == [0]


def test_structured_chunker_preserves_table_metadata() -> None:
    document = NormalizedDocument(
        source_type="xlsx",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.TABLE,
                text="Program | Duration\nBSc CS | 4 years",
                metadata={
                    "sheet": "Programs",
                    "sheet_index": 0,
                    "start_row": 1,
                    "end_row": 2,
                    "start_column": 1,
                    "end_column": 2,
                },
            ),
        ],
    )

    chunks = make_chunker().chunk(document)

    assert chunks[0].metadata["sheet"] == "Programs"
    assert chunks[0].metadata["sheet_index"] == 0
    assert chunks[0].metadata["start_row"] == 1
    assert chunks[0].metadata["end_row"] == 2


def test_structured_chunker_creates_chunk_from_key_value() -> None:
    document = NormalizedDocument(
        source_type="xlsx",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.KEY_VALUE,
                text=(
                    "Email: admissions@example.com\n"
                    "Phone: +977-1-5555555"
                ),
                metadata={
                    "sheet": "Contact",
                },
            ),
        ],
    )

    chunks = make_chunker().chunk(document)

    assert len(chunks) == 1
    assert chunks[0].element_type == NormalizedElementType.KEY_VALUE
    assert "Email: admissions@example.com" in chunks[0].text
    assert "Phone: +977-1-5555555" in chunks[0].text


def test_structured_chunker_preserves_key_value_metadata() -> None:
    document = NormalizedDocument(
        source_type="xlsx",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.KEY_VALUE,
                text="Email: admissions@example.com",
                metadata={
                    "sheet": "Contact",
                    "sheet_index": 1,
                },
            ),
        ],
    )

    chunks = make_chunker().chunk(document)

    assert chunks[0].metadata["sheet"] == "Contact"
    assert chunks[0].metadata["sheet_index"] == 1


def test_structured_chunker_ignores_prose_elements() -> None:
    document = NormalizedDocument(
        source_type="xlsx",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="This is prose.",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.TABLE,
                text="Program | Duration\nBSc CS | 4 years",
            ),
        ],
    )

    chunks = make_chunker().chunk(document)

    assert len(chunks) == 1
    assert chunks[0].element_type == NormalizedElementType.TABLE


def test_structured_chunker_ids_are_deterministic() -> None:
    document = NormalizedDocument(
        source_type="xlsx",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.TABLE,
                text="Program | Duration\nBSc CS | 4 years",
            ),
        ],
    )

    chunker = make_chunker()

    first_run = chunker.chunk(document)
    second_run = chunker.chunk(document)

    assert [chunk.id for chunk in first_run] == [
        chunk.id for chunk in second_run
    ]


def test_structured_chunker_splits_large_table() -> None:
    document = NormalizedDocument(
        source_type="xlsx",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.TABLE,
                text=(
                    "Program | Duration\n"
                    "BSc CS | 4 years\n"
                    "BBA | 4 years\n"
                    "MBA | 2 years\n"
                    "MSc IT | 2 years"
                ),
            ),
        ],
    )

    chunks = make_chunker(
        target_tokens=4,
        max_tokens=9,
        overlap_tokens=0,
    ).chunk(document)

    assert len(chunks) == 4

    assert all(
        chunk.text.startswith("Program | Duration")
        for chunk in chunks
    )

    assert "BSc CS | 4 years" in chunks[0].text
    assert "BBA | 4 years" in chunks[1].text
    assert "MBA | 2 years" in chunks[2].text
    assert "MSc IT | 2 years" in chunks[3].text

    assert all(chunk.token_count <= 9 for chunk in chunks)


def test_structured_chunker_keeps_key_value_pairs_together() -> None:
    document = NormalizedDocument(
        source_type="xlsx",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.KEY_VALUE,
                text=(
                    "Email: admissions@example.com\n"
                    "Phone: +977-1-5555555\n"
                    "Office: Kathmandu"
                ),
            ),
        ],
    )

    chunks = make_chunker(
        target_tokens=4,
        max_tokens=4,
        overlap_tokens=0,
    ).chunk(document)

    assert all(chunk.token_count <= 4 for chunk in chunks)

    for chunk in chunks:
        assert ":" in chunk.text


def test_structured_chunker_marks_oversized_table_row() -> None:
    document = NormalizedDocument(
        source_type="xlsx",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.TABLE,
                text=(
                    "Program | Description\n"
                    "BSc CS | This row contains many words "
                    "that cannot be split without breaking "
                    "the semantic meaning of the table row"
                ),
            ),
        ],
    )

    chunks = make_chunker(
        target_tokens=4,
        max_tokens=8,
        overlap_tokens=0,
    ).chunk(document)

    assert len(chunks) == 1
    assert chunks[0].token_count > 8
    assert chunks[0].metadata["token_limit"] == 8
    assert chunks[0].metadata["token_limit_exceeded"] is True


def test_structured_chunker_marks_normal_chunk_within_limit() -> None:
    document = NormalizedDocument(
        source_type="xlsx",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.KEY_VALUE,
                text=(
                    "Email: admissions@example.com\n"
                    "Phone: +977-1-5555555"
                ),
            ),
        ],
    )

    chunks = make_chunker(
        target_tokens=5,
        max_tokens=10,
        overlap_tokens=0,
    ).chunk(document)

    assert len(chunks) == 1
    assert chunks[0].token_count <= 10
    assert chunks[0].metadata["token_limit"] == 10
    assert chunks[0].metadata["token_limit_exceeded"] is False


def test_structured_table_chunk_includes_worksheet_context() -> None:
    document = NormalizedDocument(
        source_type="xlsx",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.TABLE,
                text=(
                    "Room Type | Price\n"
                    "Single | $500\n"
                    "Double | $800"
                ),
                metadata={"sheet": "Room Prices"},
            ),
        ],
    )

    chunks = make_chunker(
        target_tokens=20,
        max_tokens=30,
        overlap_tokens=0,
    ).chunk(document)

    assert len(chunks) == 1
    assert "Worksheet: Room Prices" in chunks[0].text
    assert "Room Type | Price" in chunks[0].text
    assert "Single | $500" in chunks[0].text
    assert "Double | $800" in chunks[0].text


def test_structured_table_chunks_repeat_worksheet_context_and_header() -> None:
    document = NormalizedDocument(
        source_type="xlsx",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.TABLE,
                text=(
                    "Program | Deadline\n"
                    "BBA | January 15\n"
                    "BCA | February 1\n"
                    "MBA | March 15"
                ),
                metadata={"sheet": "Admissions"},
            ),
        ],
    )

    chunks = make_chunker(
        target_tokens=4,
        max_tokens=9,
        overlap_tokens=0,
    ).chunk(document)

    assert len(chunks) > 1
    assert all("Worksheet: Admissions" in chunk.text for chunk in chunks)
    assert all("Program | Deadline" in chunk.text for chunk in chunks)
    assert "BBA | January 15" in "\n".join(c.text for c in chunks)
    assert "BCA | February 1" in "\n".join(c.text for c in chunks)
    assert "MBA | March 15" in "\n".join(c.text for c in chunks)


def test_structured_key_value_chunk_includes_worksheet_context() -> None:
    document = NormalizedDocument(
        source_type="xlsx",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.KEY_VALUE,
                text=(
                    "Name: International Office\n"
                    "Extension: 7319\n"
                    "Email: international@example.com"
                ),
                metadata={"sheet": "Contacts"},
            ),
        ],
    )

    chunks = make_chunker(
        target_tokens=20,
        max_tokens=30,
        overlap_tokens=0,
    ).chunk(document)

    assert len(chunks) == 1
    assert "Worksheet: Contacts" in chunks[0].text
    assert "Name: International Office" in chunks[0].text
    assert "Extension: 7319" in chunks[0].text
    assert "Email: international@example.com" in chunks[0].text
