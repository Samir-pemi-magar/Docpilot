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

    @staticmethod
    def _context_prefix(element: NormalizedElement) -> str:
        """Return source context that should be included in embedded text."""

        sheet = element.metadata.get("sheet")
        if sheet is None or not str(sheet).strip():
            return ""

        return f"Worksheet: {str(sheet).strip()}\n"

    def _chunk_table(
        self,
        document: NormalizedDocument,
        element: NormalizedElement,
        element_index: int,
        starting_chunk_index: int,
    ) -> list[Chunk]:
        """Split a table by rows while preserving its header and context."""

        lines = [
            line.strip()
            for line in element.text.splitlines()
            if line.strip()
        ]

        if not lines:
            return []

        header = lines[0]
        rows = lines[1:]
        context_prefix = self._context_prefix(element)

        # A table containing only a header is still a valid chunk.
        if not rows:
            return [
                self._build_chunk(
                    document=document,
                    element=element,
                    element_index=element_index,
                    text=self._join_table_rows(
                        header,
                        [],
                        context_prefix,
                    ),
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
                context_prefix,
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
                            context_prefix,
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
                        context_prefix,
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
        context_prefix = self._context_prefix(element)

        for line in lines:
            candidate_lines = [*current_lines, line]
            candidate_text = self._join_key_value_lines(
                candidate_lines,
                context_prefix,
            )

            if (
                current_lines
                and self.token_counter.count(candidate_text)
                > self.config.max_tokens
            ):
                chunks.append(
                    self._build_chunk(
                        document=document,
                        element=element,
                        element_index=element_index,
                        text=self._join_key_value_lines(
                            current_lines,
                            context_prefix,
                        ),
                        chunk_index=starting_chunk_index + len(chunks),
                    )
                )
                current_lines = []

            current_lines.append(line)

            # Preserve an oversized pair as a semantic unit, including its
            # context, and let _build_chunk mark the size-limit violation.
            rendered_text = self._join_key_value_lines(
                current_lines,
                context_prefix,
            )
            if (
                self.token_counter.count(rendered_text)
                > self.config.max_tokens
            ):
                chunks.append(
                    self._build_chunk(
                        document=document,
                        element=element,
                        element_index=element_index,
                        text=rendered_text,
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
                    text=self._join_key_value_lines(
                        current_lines,
                        context_prefix,
                    ),
                    chunk_index=starting_chunk_index + len(chunks),
                )
            )

        return chunks

    @staticmethod
    def _join_key_value_lines(
        lines: list[str],
        context_prefix: str,
    ) -> str:
        """Render key-value entries with their source context."""

        return f"{context_prefix}{chr(10).join(lines)}"

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
        context_prefix: str = "",
    ) -> str:
        """Build table text with context, header, and data rows."""

        table_text = "\n".join([header, *rows])
        return f"{context_prefix}{table_text}"
