from app.normalization.models import (
    NormalizedDocument,
    NormalizedElement,
    NormalizedElementType,
)
from app.parsers.models import ExtractedDocument


class PDFNormalizer:
    """Normalize PDF elements while preserving page and table structure."""

    def normalize(self, document: ExtractedDocument) -> NormalizedDocument:
        elements = []

        for element in document.elements:
            text = element.text.strip()
            if not text:
                continue

            if element.element_type == "table":
                element_type = NormalizedElementType.TABLE
            elif element.element_type == "heading":
                element_type = NormalizedElementType.HEADING
            else:
                element_type = NormalizedElementType.PARAGRAPH

            elements.append(
                NormalizedElement(
                    element_type=element_type,
                    text=text,
                    metadata=element.metadata.copy(),
                    content=element.content,
                )
            )

        return NormalizedDocument(
            source_type=document.source_type,
            elements=elements,
            metadata=document.metadata.copy(),
        )
