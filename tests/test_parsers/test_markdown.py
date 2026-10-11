from io import BytesIO

from app.parsers.markdown import MarkdownParser
from app.parsers.registry import ParserRegistry


def test_markdown_parser_preserves_source_text():
    source = "# Admissions\n\nThe application fee is $50.\n"
    document = MarkdownParser().parse(BytesIO(source.encode("utf-8")))

    assert document.source_type == "md"
    assert len(document.elements) == 1
    assert document.elements[0].text == source


def test_parser_registry_supports_markdown_extensions():
    registry = ParserRegistry()

    assert isinstance(registry.get_for_filename("handbook.md"), MarkdownParser)
    assert isinstance(registry.get_for_filename("handbook.markdown"), MarkdownParser)


def test_markdown_parser_accepts_utf8_bom():
    source = "\ufeff# Handbook\n\nAcademic year begins in September."
    document = MarkdownParser().parse(BytesIO(source.encode("utf-8")))

    assert document.text.startswith("# Handbook")
