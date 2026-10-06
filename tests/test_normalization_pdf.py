from pathlib import Path

from app.normalization.models import NormalizedElementType
from app.normalization.pdf import PDFNormalizer
from app.parsers.pdf import PDFParser


FIXTURE = Path("tests/fixtures/sample.pdf")


def test_pdf_normalizer_preserves_page_content():
    parser = PDFParser()
    normalizer = PDFNormalizer()

    with FIXTURE.open("rb") as file:
        extracted = parser.parse(file)

    normalized = normalizer.normalize(extracted)

    assert normalized.source_type == "pdf"
    assert len(normalized.elements) == 2

    assert normalized.elements[0].element_type == NormalizedElementType.PARAGRAPH
    assert normalized.elements[0].metadata["page_number"] == 1
    assert normalized.elements[0].text == (
        "DocPilot Test Document\n"
        "This is the first page.\n"
        "Applications open on January 1."
    )

    assert normalized.elements[1].element_type == NormalizedElementType.PARAGRAPH
    assert normalized.elements[1].metadata["page_number"] == 2
    assert normalized.elements[1].text == (
        "Admissions Information\n"
        "This is the second page.\n"
        "Applications close on March 15."
    )


def test_pdf_normalizer_preserves_document_metadata():
    parser = PDFParser()
    normalizer = PDFNormalizer()

    with FIXTURE.open("rb") as file:
        extracted = parser.parse(file)

    normalized = normalizer.normalize(extracted)

    assert normalized.metadata == extracted.metadata
    assert normalized.metadata["page_count"] == 2