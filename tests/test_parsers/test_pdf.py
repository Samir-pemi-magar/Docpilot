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


def _parse_mock_table(monkeypatch, rows, blocks):
    from io import BytesIO
    from unittest.mock import MagicMock

    from types import SimpleNamespace
    import app.parsers.pdf as pdf_module

    table = MagicMock()
    table.extract.return_value = rows
    table.bbox = (50, 200, 450, 300)
    table.header = None

    page = MagicMock()
    page.find_tables.return_value = SimpleNamespace(tables=[table])
    page.get_text.return_value = blocks

    pdf_document = MagicMock()
    pdf_document.__iter__.return_value = iter([page])
    pdf_document.__len__.return_value = 1

    monkeypatch.setattr(
        pdf_module.pymupdf, "open", lambda **kwargs: pdf_document
    )

    return PDFParser().parse(BytesIO(b"mock pdf"))


def test_pdf_table_title_prefers_explicit_table_label(monkeypatch):
    document = _parse_mock_table(
        monkeypatch,
        [["Table 1. Plan", "Amount"], ["Plan A", "$100"]],
        [(50, 120, 450, 160, "A long explanatory paragraph about plans and costs.", 0, 0)],
    )
    table = next(e for e in document.elements if e.element_type == "table")
    assert table.metadata["table_title"] == "Table 1. Plan"


def test_pdf_table_title_ignores_long_explanatory_paragraph(monkeypatch):
    document = _parse_mock_table(
        monkeypatch,
        [["Plan", "Amount"], ["Plan A", "$100"]],
        [(50, 120, 450, 160, "This long explanatory paragraph describes the plans and explains how applicants should compare their costs before selecting an option.", 0, 0)],
    )
    table = next(e for e in document.elements if e.element_type == "table")
    assert table.metadata["table_title"] is None


def test_pdf_table_title_uses_nearby_short_heading(monkeypatch):
    document = _parse_mock_table(
        monkeypatch,
        [["Plan", "Amount"], ["Plan A", "$100"]],
        [(50, 150, 300, 180, "Available Plans", 0, 0)],
    )
    table = next(e for e in document.elements if e.element_type == "table")
    assert table.metadata["table_title"] == "Available Plans"
