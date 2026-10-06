from abc import ABC, abstractmethod
from typing import BinaryIO

from app.parsers.models import ExtractedDocument


class DocumentParser(ABC):
    """Base interface for document parsers."""

    @abstractmethod
    def parse(self, file: BinaryIO) -> ExtractedDocument:
        """Parse a document and return its extracted content."""
        raise NotImplementedError