from pathlib import Path

from app.parsers.models import ExtractedDocument
from app.parsers.txt import TXTParser


FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample.txt"


def test_txt_parser_extracts_document():
    with FIXTURE_PATH.open("rb") as file:
        document = TXTParser().parse(file)

    assert isinstance(document, ExtractedDocument)

    assert document.source_type == "txt"
    assert len(document.elements) == 1

    assert document.elements[0].element_type == "paragraph"


def test_txt_parser_extracts_content():
    with FIXTURE_PATH.open("rb") as file:
        document = TXTParser().parse(file)

    text = document.elements[0].text

    assert "DocPilot Test Document" in text
    assert "This is a plain text document." in text
    assert "Admissions open on January 1." in text
    assert "Applications close on March 15." in text