from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedElement:
    """A normalized piece of content extracted from a document."""
    element_type: str
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    content: Any = None


@dataclass
class ExtractedDocument:
    """Normalized representation of extracted document content."""
    source_type: str
    elements: list[ExtractedElement] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Return all textual element content as one string."""
        return "\n\n".join(
            element.text
            for element in self.elements
            if element.text.strip()
        )
