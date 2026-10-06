from app.normalization.models import (
    NormalizedDocument,
    NormalizedElement,
    NormalizedElementType,
)
from app.parsers.models import ExtractedDocument


class PDFNormalizer:
    """Normalize PDF documents while preserving page boundaries."""

    def normalize(
        self,
        document: ExtractedDocument,
    ) -> NormalizedDocument:
        elements = []

        for element in document.elements:
            text = element.text.strip()

            if not text:
                continue

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