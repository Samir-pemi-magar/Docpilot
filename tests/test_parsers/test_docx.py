from pathlib import Path

from app.parsers.docx import DOCXParser
from app.parsers.models import ExtractedDocument


FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample.docx"


def test_docx_parser_extracts_document():
    with FIXTURE_PATH.open("rb") as file:
        document = DOCXParser().parse(file)

    assert isinstance(document, ExtractedDocument)
    assert document.source_type == "docx"

    assert document.metadata["paragraph_count"] == 6
    assert document.metadata["table_count"] == 0

    assert len(document.elements) == 6


def test_docx_parser_preserves_structure():
    with FIXTURE_PATH.open("rb") as file:
        document = DOCXParser().parse(file)

    elements = document.elements

    assert elements[0].element_type == "heading"
    assert elements[0].text == "DocPilot Admissions"
    assert elements[0].metadata["style"] == "Heading 1"

    assert elements[1].element_type == "heading"
    assert elements[1].text == "Undergraduate Applications"
    assert elements[1].metadata["style"] == "Heading 2"

    assert elements[2].element_type == "paragraph"
    assert elements[2].text == "Applications open on January 1."

    assert elements[3].element_type == "paragraph"
    assert elements[3].text == "Applications close on March 15."

    assert elements[4].element_type == "heading"
    assert elements[4].text == "Contact Information"

    assert elements[5].element_type == "paragraph"
    assert elements[5].text == "Email: admissions@example.com"


def test_docx_parser_preserves_paragraph_location():
    with FIXTURE_PATH.open("rb") as file:
        document = DOCXParser().parse(file)

    elements = document.elements

    assert elements[0].metadata["paragraph_index"] == 1
    assert elements[1].metadata["paragraph_index"] == 2
    assert elements[2].metadata["paragraph_index"] == 3
    assert elements[5].metadata["paragraph_index"] == 6
