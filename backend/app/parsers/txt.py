from typing import BinaryIO

from app.parsers.base import DocumentParser
from app.parsers.models import ExtractedDocument, ExtractedElement


class TXTParser(DocumentParser):
    """Parser for plain text documents."""

    def parse(self, file: BinaryIO) -> ExtractedDocument:
        text = file.read().decode("utf-8")

        elements = []

        if text.strip():
            elements.append(
                ExtractedElement(
                    element_type="paragraph",
                    text=text,
                )
            )

        return ExtractedDocument(
            source_type="txt",
            elements=elements,
        )