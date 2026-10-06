from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class NormalizedElementType(StrEnum):
    """Canonical semantic element types used after normalization."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    KEY_VALUE = "key_value"


@dataclass
class NormalizedElement:
    """A format-independent piece of document content."""

    element_type: NormalizedElementType
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    content: Any = None


@dataclass
class NormalizedDocument:
    """Format-independent representation of normalized document content."""

    source_type: str
    elements: list[NormalizedElement] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Return all textual content as one string."""

        return "\n\n".join(
            element.text
            for element in self.elements
            if element.text.strip()
        )
