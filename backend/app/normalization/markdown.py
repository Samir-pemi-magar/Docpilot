from app.normalization.models import NormalizedDocument
from app.normalization.txt import TXTNormalizer
from app.parsers.models import ExtractedDocument


class MarkdownNormalizer:
    """Normalize Markdown text while preserving its readable content."""

    def normalize(self, document: ExtractedDocument) -> NormalizedDocument:
        normalized = TXTNormalizer().normalize(document)
        normalized.source_type = "md"
        return normalized
