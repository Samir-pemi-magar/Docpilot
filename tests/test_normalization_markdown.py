from io import BytesIO

from app.normalization.markdown import MarkdownNormalizer
from app.normalization.registry import NormalizerRegistry
from app.parsers.markdown import MarkdownParser


def test_normalizer_registry_supports_markdown():
    normalizer = NormalizerRegistry().get_for_source_type("md")

    assert isinstance(normalizer, MarkdownNormalizer)


def test_markdown_normalization_preserves_content():
    source = (
        "# Admissions\n\n"
        "The application fee is $50.\n\n"
        "## Academic Calendar\n\n"
        "The academic year begins in September."
    )
    extracted = MarkdownParser().parse(BytesIO(source.encode("utf-8")))
    normalized = MarkdownNormalizer().normalize(extracted)

    text = "\n".join(element.text for element in normalized.elements)

    assert normalized.source_type == "md"
    assert "# Admissions" in text
    assert "The application fee is $50." in text
    assert "The academic year begins in September." in text
