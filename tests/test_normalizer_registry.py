import pytest

from app.normalization import (
    DOCXNormalizer,
    NormalizerRegistry,
    PDFNormalizer,
    TXTNormalizer,
    UnsupportedSourceTypeError,
    XLSXNormalizer,
)


def test_selects_pdf_normalizer() -> None:
    registry = NormalizerRegistry()

    normalizer = registry.get_for_source_type("pdf")

    assert isinstance(normalizer, PDFNormalizer)


def test_selects_docx_normalizer() -> None:
    registry = NormalizerRegistry()

    normalizer = registry.get_for_source_type("docx")

    assert isinstance(normalizer, DOCXNormalizer)


def test_selects_xlsx_normalizer() -> None:
    registry = NormalizerRegistry()

    normalizer = registry.get_for_source_type("xlsx")

    assert isinstance(normalizer, XLSXNormalizer)


def test_selects_txt_normalizer() -> None:
    registry = NormalizerRegistry()

    normalizer = registry.get_for_source_type("txt")

    assert isinstance(normalizer, TXTNormalizer)


def test_source_type_is_case_insensitive() -> None:
    registry = NormalizerRegistry()

    normalizer = registry.get_for_source_type("PDF")

    assert isinstance(normalizer, PDFNormalizer)


def test_rejects_unsupported_source_type() -> None:
    registry = NormalizerRegistry()

    with pytest.raises(
        UnsupportedSourceTypeError,
        match="Unsupported source type: 'csv'",
    ):
        registry.get_for_source_type("csv")


def test_registry_accepts_custom_normalizers() -> None:
    custom = TXTNormalizer()

    registry = NormalizerRegistry(
        normalizers={"custom": custom},
    )

    assert registry.get_for_source_type("custom") is custom
