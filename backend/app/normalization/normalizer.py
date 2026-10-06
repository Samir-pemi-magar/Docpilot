from app.normalization.base import DocumentNormalizer
from app.normalization.models import (
    NormalizedDocument,
    NormalizedElement,
)
from app.parsers.models import ExtractedDocument


class DefaultNormalizer(DocumentNormalizer):
    """Normalize already-structured extracted content."""

    def normalize(
        self,
        document: ExtractedDocument,
    ) -> NormalizedDocument:
        elements = []

        for element in document.elements:
            elements.append(
                NormalizedElement(
                    element_type=element.element_type,
                    text=element.text,
                    metadata=element.metadata.copy(),
                    content=element.content,
                )
            )

        return NormalizedDocument(
            source_type=document.source_type,
            elements=elements,
            metadata=document.metadata.copy(),
        )
