from app.chunking.base import Chunker
from app.chunking.models import Chunk
from app.chunking.prose import ProseChunker
from app.chunking.structured import StructuredChunker
from app.normalization.models import (
    NormalizedDocument,
    NormalizedElement,
    NormalizedElementType,
)


class HybridChunker(Chunker):
    """
    Route normalized elements to prose or structured chunking strategies.

    Prose elements:
        HEADING
        PARAGRAPH

    Structured elements:
        TABLE
        KEY_VALUE
    """

    _PROSE_TYPES = {
        NormalizedElementType.HEADING,
        NormalizedElementType.PARAGRAPH,
    }

    _STRUCTURED_TYPES = {
        NormalizedElementType.TABLE,
        NormalizedElementType.KEY_VALUE,
    }

    def __init__(
        self,
        prose_chunker: ProseChunker,
        structured_chunker: StructuredChunker,
    ) -> None:
        self.prose_chunker = prose_chunker
        self.structured_chunker = structured_chunker

    def chunk(self, document: NormalizedDocument) -> list[Chunk]:
        """Chunk a normalized document using the appropriate strategy."""

        chunks: list[Chunk] = []

        index = 0

        while index < len(document.elements):
            element = document.elements[index]

            if element.element_type in self._PROSE_TYPES:
                end = self._find_run_end(
                    document.elements,
                    index,
                    self._PROSE_TYPES,
                )

                run_elements = document.elements[index:end]
                run_document = self._make_subdocument(
                    document,
                    run_elements,
                )

                run_chunks = self.prose_chunker.chunk(run_document)

            elif element.element_type in self._STRUCTURED_TYPES:
                end = self._find_run_end(
                    document.elements,
                    index,
                    self._STRUCTURED_TYPES,
                )

                run_elements = document.elements[index:end]
                run_document = self._make_subdocument(
                    document,
                    run_elements,
                )

                run_chunks = self.structured_chunker.chunk(run_document)

            else:
                raise ValueError(
                    f"Unsupported normalized element type: "
                    f"{element.element_type!r}"
                )

            for chunk in run_chunks:
                chunk.source_element_indexes = [
                    index + source_index
                    for source_index in chunk.source_element_indexes
                    if source_index >= 0
                ]

                chunk.id = f"chunk-{len(chunks):04d}"
                chunks.append(chunk)

            index = end

        return chunks

    @staticmethod
    def _find_run_end(
        elements: list[NormalizedElement],
        start: int,
        allowed_types: set[NormalizedElementType],
    ) -> int:
        """Return the first index after a contiguous compatible run."""

        end = start

        while (
            end < len(elements)
            and elements[end].element_type in allowed_types
        ):
            end += 1

        return end

    @staticmethod
    def _make_subdocument(
        document: NormalizedDocument,
        elements: list[NormalizedElement],
    ) -> NormalizedDocument:
        """Create a normalized document for one contiguous element run."""

        return NormalizedDocument(
            source_type=document.source_type,
            elements=elements,
            metadata=document.metadata.copy(),
        )
