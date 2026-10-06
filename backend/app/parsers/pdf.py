import pymupdf
from typing import BinaryIO

from app.parsers.base import DocumentParser
from app.parsers.models import ExtractedDocument, ExtractedElement


class PDFParser(DocumentParser):
    """Parser for PDF documents."""

    def parse(self, file: BinaryIO) -> ExtractedDocument:
        document = pymupdf.open(stream=file.read(), filetype="pdf")

        try:
            elements = []

            for page_number, page in enumerate(document, start=1):
                text = page.get_text()

                if text.strip():
                    elements.append(
                        ExtractedElement(
                            element_type="paragraph",
                            text=text,
                            metadata={
                                "page_number": page_number,
                            },
                        )
                    )

            metadata = {
                "page_count": len(document),
            }

            return ExtractedDocument(
                source_type="pdf",
                elements=elements,
                metadata=metadata,
            )

        finally:
            document.close()