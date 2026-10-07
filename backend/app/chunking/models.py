from dataclasses import dataclass, field
from typing import Any

from app.normalization.models import NormalizedElementType


@dataclass
class Chunk:
    """A semantic chunk produced from normalized document content."""

    id: str
    text: str

    element_type: NormalizedElementType

    source_element_indexes: list[int] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    character_count: int = 0
    token_count: int = 0

    def __post_init__(self) -> None:
        """Populate derived character count from the chunk text."""

        self.character_count = len(self.text)


@dataclass
class ChunkedDocument:
    """Document representation containing the chunks produced by chunking."""

    source_type: str
    chunks: list[Chunk] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)