from app.normalization.base import DocumentNormalizer
from app.normalization.docx import DOCXNormalizer
from app.normalization.pdf import PDFNormalizer
from app.normalization.txt import TXTNormalizer
from app.normalization.xlsx import XLSXNormalizer


class UnsupportedSourceTypeError(ValueError):
    """Raised when no normalizer is registered for a source type."""


class NormalizerRegistry:
    """Select document normalizers based on extracted source type."""

    def __init__(
        self,
        normalizers: dict[str, DocumentNormalizer] | None = None,
    ) -> None:
        self._normalizers = normalizers or {
            "pdf": PDFNormalizer(),
            "docx": DOCXNormalizer(),
            "xlsx": XLSXNormalizer(),
            "txt": TXTNormalizer(),
        }

    def get_for_source_type(
        self,
        source_type: str,
    ) -> DocumentNormalizer:
        """Return the normalizer registered for a source type."""

        source_type = source_type.lower()

        try:
            return self._normalizers[source_type]
        except KeyError as exc:
            raise UnsupportedSourceTypeError(
                f"Unsupported source type: {source_type!r}"
            ) from exc
