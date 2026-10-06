from pathlib import Path

from app.normalization.docx import DOCXNormalizer
from app.normalization.models import NormalizedElementType
from app.parsers.docx import DOCXParser


FIXTURE = Path("tests/fixtures/sample.docx")


def test_docx_normalizer_preserves_structure():
    parser = DOCXParser()
    normalizer = DOCXNormalizer()

    with FIXTURE.open("rb") as file:
        extracted = parser.parse(file)

    normalized = normalizer.normalize(extracted)

    assert normalized.source_type == "docx"
    assert len(normalized.elements) == 6

    assert normalized.elements[0].element_type == NormalizedElementType.HEADING
    assert normalized.elements[0].text == "DocPilot Admissions"
    assert normalized.elements[0].metadata["heading_level"] == 1

    assert normalized.elements[1].element_type == NormalizedElementType.HEADING
    assert normalized.elements[1].text == "Undergraduate Applications"
    assert normalized.elements[1].metadata["heading_level"] == 2

    assert normalized.elements[2].element_type == NormalizedElementType.PARAGRAPH
    assert normalized.elements[2].text == "Applications open on January 1."

    assert normalized.elements[3].element_type == NormalizedElementType.PARAGRAPH
    assert normalized.elements[3].text == "Applications close on March 15."

    assert normalized.elements[4].element_type == NormalizedElementType.HEADING
    assert normalized.elements[4].text == "Contact Information"
    assert normalized.elements[4].metadata["heading_level"] == 2

    assert normalized.elements[5].element_type == NormalizedElementType.PARAGRAPH
    assert normalized.elements[5].text == "Email: admissions@example.com"


def test_docx_normalizer_preserves_document_metadata():
    parser = DOCXParser()
    normalizer = DOCXNormalizer()

    with FIXTURE.open("rb") as file:
        extracted = parser.parse(file)

    normalized = normalizer.normalize(extracted)

    assert normalized.metadata == extracted.metadata
