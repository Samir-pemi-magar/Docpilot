from app.chunking.config import ChunkingConfig
from app.chunking.models import Chunk
from app.chunking.tokenizer import TokenCounter
from app.normalization.models import (
    NormalizedDocument,
    NormalizedElementType,
)


class ProseChunker:
    """Chunks normalized prose while preserving heading context."""

    def __init__(
        self,
        config: ChunkingConfig,
        token_counter: TokenCounter,
    ) -> None:
        self.config = config
        self.token_counter = token_counter

    def chunk(self, document: NormalizedDocument) -> list[Chunk]:
        """Create prose chunks from a normalized document."""

        chunks: list[Chunk] = []

        heading_path: list[str] = []
        current_elements: list[tuple[int, str]] = []
        current_tokens = 0

        for index, element in enumerate(document.elements):
            if element.element_type == NormalizedElementType.HEADING:
                if current_elements:
                    chunks.append(
                        self._build_chunk(
                            document=document,
                            elements=current_elements,
                            heading_path=heading_path,
                            chunk_index=len(chunks),
                        )
                    )
                    current_elements = []
                    current_tokens = 0

                heading_path = self._update_heading_path(
                    heading_path,
                    element.text,
                )

                continue

            if element.element_type != NormalizedElementType.PARAGRAPH:
                continue

            element_tokens = self.token_counter.count(element.text)

            # A single paragraph is larger than the maximum chunk size.
            # Split it directly at the tokenizer level.
            if element_tokens > self.config.max_tokens:
                if current_elements:
                    chunks.append(
                        self._build_chunk(
                            document=document,
                            elements=current_elements,
                            heading_path=heading_path,
                            chunk_index=len(chunks),
                        )
                    )
                    current_elements = []
                    current_tokens = 0

                chunks.extend(
                    self._build_oversized_paragraph_chunks(
                        document=document,
                        element_index=index,
                        text=element.text,
                        heading_path=heading_path,
                        starting_chunk_index=len(chunks),
                    )
                )

                continue

            if (
                current_elements
                and current_tokens + element_tokens > self.config.max_tokens
            ):
                chunks.append(
                    self._build_chunk(
                        document=document,
                        elements=current_elements,
                        heading_path=heading_path,
                        chunk_index=len(chunks),
                    )
                )

                overlap_text = self.token_counter.take_last(
                    self._elements_text(current_elements),
                    self.config.overlap_tokens,
                )

                current_elements = []

                if overlap_text:
                    current_elements.append((-1, overlap_text))
                    current_tokens = self.token_counter.count(overlap_text)
                else:
                    current_tokens = 0

            current_elements.append((index, element.text))
            current_tokens += element_tokens

        if current_elements:
            chunks.append(
                self._build_chunk(
                    document=document,
                    elements=current_elements,
                    heading_path=heading_path,
                    chunk_index=len(chunks),
                )
            )

        return chunks

    def _build_oversized_paragraph_chunks(
        self,
        document: NormalizedDocument,
        element_index: int,
        text: str,
        heading_path: list[str],
        starting_chunk_index: int,
    ) -> list[Chunk]:
        """Split an oversized paragraph into size-limited chunks."""

        if self.config.overlap_tokens <= 0:
            pieces = self.token_counter.split(
                text,
                self.config.max_tokens,
            )

            return [
                self._build_chunk(
                    document=document,
                    elements=[(element_index, piece)],
                    heading_path=heading_path,
                    chunk_index=starting_chunk_index + index,
                )
                for index, piece in enumerate(pieces)
            ]

        chunks: list[Chunk] = []

        # Reconstruct the paragraph as tokens so that overlapping windows
        # can advance by max_tokens - overlap_tokens.
        tokens = text.split()
        step = self.config.max_tokens - self.config.overlap_tokens

        if step <= 0:
            raise ValueError(
                "overlap_tokens must be smaller than max_tokens"
            )

        for start in range(0, len(tokens), step):
            piece = " ".join(
                tokens[start:start + self.config.max_tokens]
            )

            if not piece:
                break

            chunks.append(
                self._build_chunk(
                    document=document,
                    elements=[(element_index, piece)],
                    heading_path=heading_path,
                    chunk_index=starting_chunk_index + len(chunks),
                )
            )

            if start + self.config.max_tokens >= len(tokens):
                break

        return chunks

    def _build_chunk(
        self,
        document: NormalizedDocument,
        elements: list[tuple[int, str]],
        heading_path: list[str],
        chunk_index: int,
    ) -> Chunk:
        """Build a chunk from normalized paragraph elements."""

        paragraph_text = "\n\n".join(
            text for _, text in elements if text.strip()
        )

        if heading_path:
            text = (
                "\n".join(heading_path)
                + "\n\n"
                + paragraph_text
            )
        else:
            text = paragraph_text

        source_indexes = [
            index
            for index, _ in elements
            if index >= 0
        ]

        metadata = {
            "heading_path": list(heading_path),
            "source_type": document.source_type,
        }

        return Chunk(
            id=f"chunk-{chunk_index:04d}",
            text=text,
            element_type=NormalizedElementType.PARAGRAPH,
            source_element_indexes=source_indexes,
            metadata=metadata,
            token_count=self.token_counter.count(text),
        )

    @staticmethod
    def _elements_text(
        elements: list[tuple[int, str]],
    ) -> str:
        """Return the text represented by the current elements."""

        return "\n\n".join(
            text for _, text in elements if text.strip()
        )

    @staticmethod
    def _update_heading_path(
        current_path: list[str],
        heading: str,
    ) -> list[str]:
        """Update heading context.

        The current normalized representation does not contain heading
        levels, so each heading replaces the previous heading context.
        """

        return [heading]
