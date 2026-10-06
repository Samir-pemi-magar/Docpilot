from pathlib import Path

from app.normalization.models import NormalizedElementType
from app.normalization.txt import TXTNormalizer
from app.parsers.txt import TXTParser


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_txt_normalizer_splits_paragraphs():
    with (FIXTURES_DIR / "sample.txt").open("rb") as file:
        extracted = TXTParser().parse(file)

    normalized = TXTNormalizer().normalize(extracted)

    assert len(normalized.elements) == 3

    assert all(
        element.element_type == NormalizedElementType.PARAGRAPH
        for element in normalized.elements
    )

    assert normalized.elements[0].text == "DocPilot Test Document"

    assert normalized.elements[1].text == (
        "This is a plain text document."
    )

    assert normalized.elements[2].text == (
        "Admissions open on January 1.\n"
        "Applications close on March 15."
    )


def test_txt_normalizer_preserves_source_metadata():
    with (FIXTURES_DIR / "sample.txt").open("rb") as file:
        extracted = TXTParser().parse(file)

    normalized = TXTNormalizer().normalize(extracted)

    assert normalized.source_type == "txt"
    assert normalized.metadata == extracted.metadata
