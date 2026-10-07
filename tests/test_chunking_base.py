from app.chunking.base import Chunker
from app.chunking.config import ChunkingConfig
from app.chunking.prose import ProseChunker
from app.chunking.tokenizer import SimpleTokenCounter
from app.normalization.models import (
    NormalizedDocument,
    NormalizedElement,
    NormalizedElementType,
)


def test_prose_chunker_implements_chunker_protocol() -> None:
    chunker: Chunker = ProseChunker(
        config=ChunkingConfig(),
        token_counter=SimpleTokenCounter(),
    )

    document = NormalizedDocument(
        source_type="txt",
        elements=[
            NormalizedElement(
                element_type=NormalizedElementType.PARAGRAPH,
                text="Hello world.",
            ),
        ],
    )

    chunks = chunker.chunk(document)

    assert len(chunks) == 1
    assert chunks[0].text == "Hello world."
