from app.chunking.config import ChunkingConfig
from app.chunking.models import Chunk
from app.chunking.tokenizer import TokenCounter
from app.normalization.models import (
    NormalizedDocument,
    NormalizedElement,
    NormalizedElementType,
)


class StructuredChunker:
    """Chunk structured table and key-value elements."""

    def __init__(
        self,
        config: ChunkingConfig,
        token_counter: TokenCounter,
    ) -> None:
        self.config = config
        self.token_counter = token_counter

    def chunk(self, document: NormalizedDocument) -> list[Chunk]:
        """Create chunks from table and key-value elements."""

        chunks: list[Chunk] = []

        for index, element in enumerate(document.elements):
            if element.element_type == NormalizedElementType.TABLE:
                chunks.extend(
                    self._chunk_table(
                        document=document,
                        element=element,
                        element_index=index,
                        starting_chunk_index=len(chunks),
                    )
                )

            elif element.element_type == NormalizedElementType.KEY_VALUE:
                chunks.extend(
                    self._chunk_key_value(
                        document=document,
                        element=element,
                        element_index=index,
                        starting_chunk_index=len(chunks),
                    )
                )

        return chunks

    def _chunk_table(
        self,
        document: NormalizedDocument,
        element: NormalizedElement,
        element_index: int,
        starting_chunk_index: int,
    ) -> list[Chunk]:
        """Split a table by rows while preserving its header."""

        lines = [
            line.strip()
            for line in element.text.splitlines()
            if line.strip()
        ]

        if not lines:
            return []

        header = lines[0]
        rows = lines[1:]

        # A table containing only a header is still a valid chunk.
        if not rows:
            return [
                self._build_chunk(
                    document=document,
                    element=element,
                    element_index=element_index,
                    text=header,
                    chunk_index=starting_chunk_index,
                )
            ]

        chunks: list[Chunk] = []
        current_rows: list[str] = []

        for row in rows:
            candidate_rows = [*current_rows, row]
            candidate_text = self._join_table_rows(
                header,
                candidate_rows,
            )

            if (
                current_rows
                and self.token_counter.count(candidate_text)
                > self.config.max_tokens
            ):
                chunks.append(
                    self._build_chunk(
                        document=document,
                        element=element,
                        element_index=element_index,
                        text=self._join_table_rows(
                            header,
                            current_rows,
                        ),
                        chunk_index=starting_chunk_index + len(chunks),
                    )
                )

                current_rows = [row]
                continue

            current_rows.append(row)

        if current_rows:
            chunks.append(
                self._build_chunk(
                    document=document,
                    element=element,
                    element_index=element_index,
                    text=self._join_table_rows(
                        header,
                        current_rows,
                    ),
                    chunk_index=starting_chunk_index + len(chunks),
                )
            )

        return chunks

    def _chunk_key_value(
        self,
        document: NormalizedDocument,
        element: NormalizedElement,
        element_index: int,
        starting_chunk_index: int,
    ) -> list[Chunk]:
        """Split key-value entries while keeping each pair together."""

        lines = [
            line.strip()
            for line in element.text.splitlines()
            if line.strip()
        ]

        if not lines:
            return []

        chunks: list[Chunk] = []
        current_lines: list[str] = []

        for line in lines:
            line_tokens = self.token_counter.count(line)

            if (
                current_lines
                and self.token_counter.count(
                    "\n".join([*current_lines, line])
                ) > self.config.max_tokens
            ):
                chunks.append(
                    self._build_chunk(
                        document=document,
                        element=element,
                        element_index=element_index,
                        text="\n".join(current_lines),
                        chunk_index=starting_chunk_index + len(chunks),
                    )
                )

                current_lines = [line]
                continue

            # A single key-value pair can itself exceed max_tokens.
            # In that case we preserve the pair as one semantic unit.
            current_lines.append(line)

            if line_tokens > self.config.max_tokens:
                chunks.append(
                    self._build_chunk(
                        document=document,
                        element=element,
                        element_index=element_index,
                        text="\n".join(current_lines),
                        chunk_index=starting_chunk_index + len(chunks),
                    )
                )
                current_lines = []

        if current_lines:
            chunks.append(
                self._build_chunk(
                    document=document,
                    element=element,
                    element_index=element_index,
                    text="\n".join(current_lines),
                    chunk_index=starting_chunk_index + len(chunks),
                )
            )

        return chunks

    def _build_chunk(
        self,
        document: NormalizedDocument,
        element: NormalizedElement,
        element_index: int,
        text: str,
        chunk_index: int,
    ) -> Chunk:
        """Build a chunk while preserving source metadata."""

        token_count = self.token_counter.count(text)

        metadata = element.metadata.copy()
        metadata["source_type"] = document.source_type
        metadata["token_limit"] = self.config.max_tokens
        metadata["token_limit_exceeded"] = (
            token_count > self.config.max_tokens
        )

        return Chunk(
            id=f"chunk-{chunk_index:04d}",
            text=text,
            element_type=element.element_type,
            source_element_indexes=[element_index],
            metadata=metadata,
            token_count=token_count,
        )

    @staticmethod
    def _join_table_rows(
        header: str,
        rows: list[str],
    ) -> str:
        """Build table text with the header followed by data rows."""

        return "\n".join([header, *rows])
