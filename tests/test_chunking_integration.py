from app.chunking import (
    ChunkingConfig,
    ProseChunker,
    SimpleTokenCounter,
    StructuredChunker,
)
from app.normalization.models import (
    NormalizedDocument,
    NormalizedElement,
    NormalizedElementType,
)


def test_chunkers_handle_mixed_normalized_document() -> None:
    document = NormalizedDocument(
        source_type="xlsx",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.HEADING,
                text="Admissions",
            ),
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text=(
                    "Applications are accepted throughout the year. "
                    "Students should submit all required documents."
                ),
            ),
            NormalizedElement(
                element_type=NormalizedElementType.TABLE,
                text=(
                    "Program | Duration\n"
                    "BSc CS | 4 years\n"
                    "BBA | 4 years"
                ),
                metadata={"sheet": "Programs"},
            ),
            NormalizedElement(
                element_type=NormalizedElementType.KEY_VALUE,
                text=(
                    "Email: admissions@example.com\n"
                    "Phone: +977-1-5555555"
                ),
                metadata={"sheet": "Contact"},
            ),
        ],
    )

    config = ChunkingConfig(
        target_tokens=10,
        max_tokens=20,
        overlap_tokens=0,
    )

    token_counter = SimpleTokenCounter()

    prose_chunker = ProseChunker(
        config=config,
        token_counter=token_counter,
    )

    structured_chunker = StructuredChunker(
        config=config,
        token_counter=token_counter,
    )

    prose_chunks = prose_chunker.chunk(document)
    structured_chunks = structured_chunker.chunk(document)

    assert len(prose_chunks) == 1
    assert prose_chunks[0].element_type == NormalizedElementType.PARAGRAPH
    assert prose_chunks[0].metadata["heading_path"] == ["Admissions"]

    assert len(structured_chunks) == 2

    assert structured_chunks[0].element_type == NormalizedElementType.TABLE
    assert structured_chunks[0].metadata["sheet"] == "Programs"

    assert structured_chunks[1].element_type == NormalizedElementType.KEY_VALUE
    assert structured_chunks[1].metadata["sheet"] == "Contact"
