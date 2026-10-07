from pathlib import Path

from app.parsers.base import DocumentParser
from app.parsers.docx import DOCXParser
from app.parsers.pdf import PDFParser
from app.parsers.txt import TXTParser
from app.parsers.xlsx import XLSXParser


class UnsupportedDocumentTypeError(ValueError):
    """Raised when no parser is registered for a document type."""


class ParserRegistry:
    """Select document parsers based on file extension."""

    def __init__(
        self,
        parsers: dict[str, DocumentParser] | None = None,
    ) -> None:
        self._parsers = parsers or {
            ".pdf": PDFParser(),
            ".docx": DOCXParser(),
            ".xlsx": XLSXParser(),
            ".txt": TXTParser(),
        }

    def get_for_filename(self, filename: str) -> DocumentParser:
        """Return the parser registered for a filename."""

        suffix = Path(filename).suffix.lower()

        try:
            return self._parsers[suffix]
        except KeyError as exc:
            raise UnsupportedDocumentTypeError(
                f"Unsupported document type: {suffix or '<none>'}"
            ) from exc
