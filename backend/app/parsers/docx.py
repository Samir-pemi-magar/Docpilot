from typing import BinaryIO

from docx import Document

from app.parsers.base import DocumentParser
from app.parsers.models import ExtractedDocument, ExtractedElement


class DOCXParser(DocumentParser):
    """Parser for Microsoft Word documents."""

    def parse(self, file: BinaryIO) -> ExtractedDocument:
        document = Document(file)

        elements = []

        for paragraph_index, paragraph in enumerate(
            document.paragraphs,
            start=1,
        ):
            text = paragraph.text.strip()

            if not text:
                continue

            style_name = paragraph.style.name

            if style_name.startswith("Heading"):
                element_type = "heading"
            else:
                element_type = "paragraph"

            elements.append(
                ExtractedElement(
                    element_type=element_type,
                    text=text,
                    metadata={
                        "paragraph_index": paragraph_index,
                        "style": style_name,
                    },
                )
            )

        metadata = {
            "paragraph_count": len(document.paragraphs),
            "table_count": len(document.tables),
        }

        return ExtractedDocument(
            source_type="docx",
            elements=elements,
            metadata=metadata,
        )
