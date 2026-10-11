from typing import BinaryIO

from app.parsers.base import DocumentParser
from app.parsers.models import ExtractedDocument, ExtractedElement


class MarkdownParser(DocumentParser):
    """Parse Markdown files while preserving their source text."""

    def parse(self, file: BinaryIO) -> ExtractedDocument:
        text = file.read().decode("utf-8-sig")

        elements = []
        if text.strip():
            elements.append(
                ExtractedElement(
                    element_type="paragraph",
                    text=text,
                )
            )

        return ExtractedDocument(
            source_type="md",
            elements=elements,
        )
