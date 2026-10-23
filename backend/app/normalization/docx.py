from app.normalization.models import (
    NormalizedDocument,
    NormalizedElement,
    NormalizedElementType,
)
from app.parsers.models import ExtractedDocument


class DOCXNormalizer:
    """Normalize DOCX documents while preserving heading hierarchy."""

    def normalize(
        self,
        document: ExtractedDocument,
    ) -> NormalizedDocument:
        elements = []

        for element in document.elements:
            text = element.text.strip()

            if not text:
                continue

            if element.element_type == "heading":
                style = element.metadata.get("style", "")
                heading_level = self._get_heading_level(style)

                metadata = element.metadata.copy()
                metadata["heading_level"] = heading_level

                elements.append(
                    NormalizedElement(
                        element_type=NormalizedElementType.HEADING,
                        text=text,
                        metadata=metadata,
                    )
                )

            elif element.element_type == "table":
                elements.append(
                    NormalizedElement(
                        element_type=NormalizedElementType.TABLE,
                        text=text,
                        metadata=element.metadata.copy(),
                        content=element.content,
                    )
                )

            elif element.element_type == "paragraph":
                elements.append(
                    NormalizedElement(
                        element_type=NormalizedElementType.PARAGRAPH,
                        text=text,
                        metadata=element.metadata.copy(),
                    )
                )

        return NormalizedDocument(
            source_type=document.source_type,
            elements=elements,
            metadata=document.metadata.copy(),
        )

    def _get_heading_level(self, style: str) -> int | None:
        """Extract the heading level from a DOCX heading style."""

        if not style.startswith("Heading"):
            return None

        try:
            return int(style.removeprefix("Heading").strip())
        except ValueError:
            return None
