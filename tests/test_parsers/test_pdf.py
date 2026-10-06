from pathlib import Path

from app.parsers.models import ExtractedDocument
from app.parsers.pdf import PDFParser


FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample.pdf"


def test_pdf_parser_extracts_document():
    with FIXTURE_PATH.open("rb") as file:
        document = PDFParser().parse(file)

    assert isinstance(document, ExtractedDocument)

    assert document.source_type == "pdf"
    assert document.metadata["page_count"] == 2

    assert len(document.elements) == 2


def test_pdf_parser_extracts_page_content():
    with FIXTURE_PATH.open("rb") as file:
        document = PDFParser().parse(file)

    first_element = document.elements[0]
    second_element = document.elements[1]

    assert first_element.element_type == "paragraph"
    assert second_element.element_type == "paragraph"

    assert first_element.metadata["page_number"] == 1
    assert second_element.metadata["page_number"] == 2

    assert "DocPilot Test Document" in first_element.text
    assert "Applications open on January 1." in first_element.text

    assert "Admissions Information" in second_element.text
    assert "Applications close on March 15." in second_element.text