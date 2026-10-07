from app.chunking.config import ChunkingConfig
from app.chunking.hybrid import HybridChunker
from app.chunking.prose import ProseChunker
from app.chunking.structured import StructuredChunker
from app.chunking.tokenizer import SimpleTokenCounter
from app.normalization.models import (
    NormalizedDocument,
    NormalizedElement,
    NormalizedElementType,
)


def make_chunker() -> HybridChunker:
    token_counter = SimpleTokenCounter()
    config = ChunkingConfig(
        target_tokens=10,
        max_tokens=20,
        overlap_tokens=2,
    )

    return HybridChunker(
        prose_chunker=ProseChunker(
            config=config,
            token_counter=token_counter,
        ),
        structured_chunker=StructuredChunker(
            config=config,
            token_counter=token_counter,
        ),
    )


def test_hybrid_chunker_routes_prose_and_structured_elements() -> None:
    document = NormalizedDocument(
        source_type="mixed",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.HEADING,
                text="Introduction",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="This is the introduction.",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.TABLE,
                text="Name | Role\nAlice | Admin\nBob | Member",
                content={
                    "headers": ["Name", "Role"],
                    "rows": [
                        ["Alice", "Admin"],
                        ["Bob", "Member"],
                    ],
                },
                metadata={"sheet": "Users"},
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="This comes after the table.",
            ),
        ],
    )

    chunks = make_chunker().chunk(document)

    assert len(chunks) == 3

    assert chunks[0].element_type == NormalizedElementType.PARAGRAPH
    assert chunks[0].source_element_indexes == [1]

    assert chunks[1].element_type == NormalizedElementType.TABLE
    assert chunks[1].source_element_indexes == [2]

    assert chunks[2].element_type == NormalizedElementType.PARAGRAPH
    assert chunks[2].source_element_indexes == [3]


def test_hybrid_chunker_assigns_global_chunk_ids() -> None:
    document = NormalizedDocument(
        source_type="mixed",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="First paragraph.",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.TABLE,
                text="Name | Role\nAlice | Admin",
                content={
                    "headers": ["Name", "Role"],
                    "rows": [
                        ["Alice", "Admin"],
                    ],
                },
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="Last paragraph.",
            ),
        ],
    )

    chunks = make_chunker().chunk(document)

    assert [chunk.id for chunk in chunks] == [
        "chunk-0000",
        "chunk-0001",
        "chunk-0002",
    ]


def test_hybrid_chunker_preserves_document_order() -> None:
    document = NormalizedDocument(
        source_type="mixed",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="Before.",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.TABLE,
                text="A | B\n1 | 2",
                content={
                    "headers": ["A", "B"],
                    "rows": [["1", "2"]],
                },
            ),
            NormalizedElement(
                element_type=NormalizedElementType.KEY_VALUE,
                text="Status: Active",
                content={
                    "key": "Status",
                    "value": "Active",
                },
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="After.",
            ),
        ],
    )

    chunks = make_chunker().chunk(document)

    assert [
        min(chunk.source_element_indexes)
        for chunk in chunks
    ] == [0, 1, 2, 3]


def test_hybrid_chunker_handles_multiple_chunks_in_one_prose_run() -> None:
    document = NormalizedDocument(
        source_type="mixed",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty twentyone twentytwo twentythree twentyfour twentyfive",
            ),
        ],
    )

    chunks = make_chunker().chunk(document)

    assert len(chunks) == 2
    assert [chunk.id for chunk in chunks] == [
        "chunk-0000",
        "chunk-0001",
    ]
    assert chunks[0].source_element_indexes == [0]
    assert chunks[1].source_element_indexes == [0]


def test_hybrid_chunker_handles_multiple_structured_chunks() -> None:
    document = NormalizedDocument(
        source_type="mixed",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.TABLE,
                text=(
                    "Name | Role\n"
                    "Alice | Administrator\n"
                    "Bob | Member\n"
                    "Charlie | Viewer\n"
                    "David | Editor\n"
                    "Eve | Manager\n"
                    "Frank | Developer\n"
                    "Grace | Analyst\n"
                    "Henry | Supervisor\n"
                    "Ivy | Coordinator\n"
                ),
            ),
        ],
    )

    chunks = make_chunker().chunk(document)

    assert len(chunks) > 1

    assert all(
        chunk.element_type == NormalizedElementType.TABLE
        for chunk in chunks
    )

    assert all(
        chunk.source_element_indexes == [0]
        for chunk in chunks
    )


def test_hybrid_chunker_preserves_indexes_across_multiple_runs() -> None:
    document = NormalizedDocument(
        source_type="mixed",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="one two three four five six seven eight nine ten",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.TABLE,
                text="Name | Role\nAlice | Admin\nBob | Member",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="Final paragraph.",
            ),
        ],
    )

    chunks = make_chunker().chunk(document)

    assert chunks[0].source_element_indexes == [0]
    assert chunks[1].source_element_indexes == [1]
    assert chunks[2].source_element_indexes == [2]


def test_hybrid_chunker_returns_empty_for_empty_document() -> None:
    document = NormalizedDocument(
        source_type="mixed",
        elements=[],
    )

    chunks = make_chunker().chunk(document)

    assert chunks == []


def test_hybrid_chunker_rejects_unsupported_element_type() -> None:
    document = NormalizedDocument(
        source_type="mixed",
        elements=[
            NormalizedElement(
                element_type="unsupported",  # type: ignore[arg-type]
                text="Unexpected content.",
            ),
        ],
    )

    try:
        make_chunker().chunk(document)
    except ValueError as exc:
        assert "Unsupported normalized element type" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
