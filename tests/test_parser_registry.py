import pytest

from app.parsers import (
    DOCXParser,
    PDFParser,
    ParserRegistry,
    TXTParser,
    UnsupportedDocumentTypeError,
    XLSXParser,
)


def test_parser_registry_selects_pdf_parser() -> None:
    registry = ParserRegistry()

    parser = registry.get_for_filename("document.pdf")

    assert isinstance(parser, PDFParser)


def test_parser_registry_selects_docx_parser() -> None:
    registry = ParserRegistry()

    parser = registry.get_for_filename("document.docx")

    assert isinstance(parser, DOCXParser)


def test_parser_registry_selects_xlsx_parser() -> None:
    registry = ParserRegistry()

    parser = registry.get_for_filename("document.xlsx")

    assert isinstance(parser, XLSXParser)


def test_parser_registry_selects_txt_parser() -> None:
    registry = ParserRegistry()

    parser = registry.get_for_filename("document.txt")

    assert isinstance(parser, TXTParser)


def test_parser_registry_is_case_insensitive() -> None:
    registry = ParserRegistry()

    assert isinstance(
        registry.get_for_filename("document.PDF"),
        PDFParser,
    )


def test_parser_registry_rejects_unsupported_extension() -> None:
    registry = ParserRegistry()

    with pytest.raises(
        UnsupportedDocumentTypeError,
        match="Unsupported document type: .csv",
    ):
        registry.get_for_filename("document.csv")


def test_parser_registry_rejects_filename_without_extension() -> None:
    registry = ParserRegistry()

    with pytest.raises(
        UnsupportedDocumentTypeError,
        match="Unsupported document type: <none>",
    ):
        registry.get_for_filename("document")
