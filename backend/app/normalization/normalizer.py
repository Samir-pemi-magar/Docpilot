from app.normalization.base import DocumentNormalizer
from app.normalization.models import (
    NormalizedDocument,
    NormalizedElement,
    NormalizedElementType,
)
from app.parsers.models import ExtractedDocument, ExtractedElement


class DefaultNormalizer(DocumentNormalizer):
    """Normalize extracted document content into canonical elements."""

    _ELEMENT_TYPE_MAP = {
        "heading": NormalizedElementType.HEADING,
        "paragraph": NormalizedElementType.PARAGRAPH,
        "worksheet": NormalizedElementType.TABLE,
    }

    def normalize(
        self,
        document: ExtractedDocument,
    ) -> NormalizedDocument:
        elements = [
            self._normalize_element(element)
            for element in document.elements
        ]

        return NormalizedDocument(
            source_type=document.source_type,
            elements=elements,
            metadata=document.metadata.copy(),
        )

    @classmethod
    def _normalize_element(
        cls,
        element: ExtractedElement,
    ) -> NormalizedElement:
        try:
            element_type = cls._ELEMENT_TYPE_MAP[element.element_type]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported extracted element type: "
                f"{element.element_type!r}"
            ) from exc

        return NormalizedElement(
            element_type=element_type,
            text=element.text,
            metadata=element.metadata.copy(),
            content=element.content,
        )
