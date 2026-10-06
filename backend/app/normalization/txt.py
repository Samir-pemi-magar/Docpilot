from app.normalization.models import (
    NormalizedDocument,
    NormalizedElement,
    NormalizedElementType,
)
from app.parsers.models import ExtractedDocument


class TXTNormalizer:
    """Normalize plain-text documents into paragraphs."""

    def normalize(
        self,
        document: ExtractedDocument,
    ) -> NormalizedDocument:
        elements = []

        for element in document.elements:
            if not element.text.strip():
                continue

            paragraphs = [
                paragraph.strip()
                for paragraph in element.text.split("\n\n")
                if paragraph.strip()
            ]

            for paragraph in paragraphs:
                elements.append(
                    NormalizedElement(
                        element_type=NormalizedElementType.PARAGRAPH,
                        text=paragraph,
                        metadata=element.metadata.copy(),
                    )
                )

        return NormalizedDocument(
            source_type=document.source_type,
            elements=elements,
            metadata=document.metadata.copy(),
        )
