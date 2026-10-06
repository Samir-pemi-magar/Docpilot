from pathlib import Path

from app.normalization.models import NormalizedDocument
from app.normalization.normalizer import DefaultNormalizer
from app.parsers.docx import DOCXParser
from app.parsers.pdf import PDFParser
from app.parsers.txt import TXTParser


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_default_normalizer_normalizes_txt_document():
    with (FIXTURES_DIR / "sample.txt").open("rb") as file:
        extracted = TXTParser().parse(file)

    normalized = DefaultNormalizer().normalize(extracted)

    assert isinstance(normalized, NormalizedDocument)
    assert normalized.source_type == "txt"
    assert len(normalized.elements) == 1

    element = normalized.elements[0]

    assert element.element_type == "paragraph"
    assert "DocPilot Test Document" in element.text
    assert "Admissions open on January 1." in element.text
    assert "Applications close on March 15." in element.text


def test_default_normalizer_normalizes_pdf_document():
    with (FIXTURES_DIR / "sample.pdf").open("rb") as file:
        extracted = PDFParser().parse(file)

    normalized = DefaultNormalizer().normalize(extracted)

    assert isinstance(normalized, NormalizedDocument)
    assert normalized.source_type == "pdf"
    assert len(normalized.elements) == 2

    first_element = normalized.elements[0]
    second_element = normalized.elements[1]

    assert first_element.element_type == "paragraph"
    assert second_element.element_type == "paragraph"

    assert first_element.metadata["page_number"] == 1
    assert second_element.metadata["page_number"] == 2

    assert "DocPilot Test Document" in first_element.text
    assert "Admissions Information" in second_element.text


def test_default_normalizer_normalizes_docx_document():
    with (FIXTURES_DIR / "sample.docx").open("rb") as file:
        extracted = DOCXParser().parse(file)

    normalized = DefaultNormalizer().normalize(extracted)

    assert isinstance(normalized, NormalizedDocument)
    assert normalized.source_type == "docx"
    assert len(normalized.elements) == 6

    first_element = normalized.elements[0]
    second_element = normalized.elements[1]

    assert first_element.element_type == "heading"
    assert second_element.element_type == "heading"

    assert first_element.text == "DocPilot Admissions"
    assert second_element.text == "Undergraduate Applications"

    assert first_element.metadata["paragraph_index"] == 1
    assert second_element.metadata["paragraph_index"] == 2
