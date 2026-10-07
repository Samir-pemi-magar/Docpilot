from app.chunking.config import ChunkingConfig
from app.chunking.prose import ProseChunker
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
) -> ProseChunker:
    return ProseChunker(
        config=ChunkingConfig(
            target_tokens=target_tokens,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        ),
        token_counter=SimpleTokenCounter(),
    )


def test_prose_chunker_creates_chunk_from_paragraphs() -> None:
    document = NormalizedDocument(
        source_type="txt",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="Applications open January 1.",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="Applications close March 15.",
            ),
        ],
    )

    chunks = make_chunker().chunk(document)

    assert len(chunks) == 1
    assert "Applications open January 1." in chunks[0].text
    assert "Applications close March 15." in chunks[0].text


def test_prose_chunker_preserves_source_indexes() -> None:
    document = NormalizedDocument(
        source_type="txt",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="First paragraph.",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="Second paragraph.",
            ),
        ],
    )

    chunks = make_chunker().chunk(document)

    assert chunks[0].source_element_indexes == [0, 1]


def test_prose_chunker_propagates_heading() -> None:
    document = NormalizedDocument(
        source_type="pdf",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.HEADING,
                text="Admissions",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="Applications open January 1.",
            ),
        ],
    )

    chunks = make_chunker().chunk(document)

    assert len(chunks) == 1
    assert chunks[0].text == (
        "Admissions\n\n"
        "Applications open January 1."
    )
    assert chunks[0].metadata["heading_path"] == ["Admissions"]


def test_new_heading_replaces_previous_heading() -> None:
    document = NormalizedDocument(
        source_type="pdf",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.HEADING,
                text="Admissions",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="Apply online.",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.HEADING,
                text="Tuition",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="Tuition is $1000.",
            ),
        ],
    )

    chunks = make_chunker().chunk(document)

    assert len(chunks) == 2

    assert chunks[0].metadata["heading_path"] == ["Admissions"]
    assert chunks[1].metadata["heading_path"] == ["Tuition"]


def test_prose_chunker_splits_when_max_tokens_exceeded() -> None:
    document = NormalizedDocument(
        source_type="txt",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="one two three four",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="five six seven eight",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="nine ten eleven twelve",
            ),
        ],
    )

    chunks = make_chunker(
        target_tokens=5,
        max_tokens=6,
    ).chunk(document)

    assert len(chunks) == 3
    assert chunks[0].source_element_indexes == [0]
    assert chunks[1].source_element_indexes == [1]
    assert chunks[2].source_element_indexes == [2]


def test_prose_chunk_ids_are_deterministic() -> None:
    document = NormalizedDocument(
        source_type="txt",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="First paragraph.",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="Second paragraph.",
            ),
        ],
    )

    chunker = make_chunker()

    first_run = chunker.chunk(document)
    second_run = chunker.chunk(document)

    assert [chunk.id for chunk in first_run] == [
        chunk.id for chunk in second_run
    ]

def test_prose_chunker_applies_overlap() -> None:
    document = NormalizedDocument(
        source_type="txt",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="one two three four",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="five six seven eight",
            ),
        ],
    )

    chunks = make_chunker(
        target_tokens=4,
        max_tokens=6,
        overlap_tokens=2,
    ).chunk(document)

    assert len(chunks) == 2
    assert chunks[0].text == "one two three four"
    assert "three four" in chunks[1].text
    assert "five six seven eight" in chunks[1].text


def test_prose_chunker_zero_overlap_preserves_previous_behavior() -> None:
    document = NormalizedDocument(
        source_type="txt",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="one two three four",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="five six seven eight",
            ),
        ],
    )

    chunks = make_chunker(
        target_tokens=4,
        max_tokens=6,
        overlap_tokens=0,
    ).chunk(document)

    assert len(chunks) == 2
    assert chunks[0].text == "one two three four"
    assert chunks[1].text == "five six seven eight"


def test_overlap_does_not_create_source_element_indexes() -> None:
    document = NormalizedDocument(
        source_type="txt",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="one two three four",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="five six seven eight",
            ),
        ],
    )

    chunks = make_chunker(
        target_tokens=4,
        max_tokens=6,
        overlap_tokens=2,
    ).chunk(document)

    assert chunks[0].source_element_indexes == [0]
    assert chunks[1].source_element_indexes == [1]

def test_prose_chunker_splits_oversized_paragraph() -> None:
    document = NormalizedDocument(
        source_type="txt",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="one two three four five six seven eight nine ten",
            ),
        ],
    )

    chunks = make_chunker(
        target_tokens=4,
        max_tokens=4,
        overlap_tokens=0,
    ).chunk(document)

    assert len(chunks) == 3

    assert chunks[0].text == "one two three four"
    assert chunks[1].text == "five six seven eight"
    assert chunks[2].text == "nine ten"

    assert chunks[0].token_count == 4
    assert chunks[1].token_count == 4
    assert chunks[2].token_count == 2

    assert chunks[0].source_element_indexes == [0]
    assert chunks[1].source_element_indexes == [0]
    assert chunks[2].source_element_indexes == [0]


def test_prose_chunker_splits_oversized_paragraph_with_overlap() -> None:
    document = NormalizedDocument(
        source_type="txt",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="one two three four five six seven eight",
            ),
        ],
    )

    chunks = make_chunker(
        target_tokens=4,
        max_tokens=4,
        overlap_tokens=1,
    ).chunk(document)

    assert len(chunks) == 3

    assert chunks[0].text == "one two three four"
    assert chunks[1].text == "four five six seven"
    assert chunks[2].text == "seven eight"

    assert all(chunk.token_count <= 4 for chunk in chunks)

    assert chunks[0].source_element_indexes == [0]
    assert chunks[1].source_element_indexes == [0]
    assert chunks[2].source_element_indexes == [0]
