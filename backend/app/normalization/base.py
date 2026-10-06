from abc import ABC, abstractmethod

from app.parsers.models import ExtractedDocument
from app.normalization.models import NormalizedDocument


class DocumentNormalizer(ABC):
    """Base interface for document normalizers."""

    @abstractmethod
    def normalize(
        self,
        document: ExtractedDocument,
    ) -> NormalizedDocument:
        """Normalize extracted document content."""
        raise NotImplementedError
