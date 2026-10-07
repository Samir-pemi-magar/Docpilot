from typing import BinaryIO

from app.chunking.base import Chunker
from app.normalization.registry import NormalizerRegistry
from app.parsers.registry import ParserRegistry
from app.processing.models import ProcessingResult


class DocumentProcessingPipeline:
    """Orchestrate parsing, normalization, and chunking."""

    def __init__(
        self,
        parser_registry: ParserRegistry,
        normalizer_registry: NormalizerRegistry,
        chunker: Chunker,
    ) -> None:
        self.parser_registry = parser_registry
        self.normalizer_registry = normalizer_registry
        self.chunker = chunker

    def process(
        self,
        filename: str,
        file: BinaryIO,
    ) -> ProcessingResult:
        """Parse, normalize, and chunk a document."""

        parser = self.parser_registry.get_for_filename(filename)

        extracted_document = parser.parse(file)

        normalizer = self.normalizer_registry.get_for_source_type(
            extracted_document.source_type
        )

        normalized_document = normalizer.normalize(
            extracted_document
        )

        chunks = self.chunker.chunk(normalized_document)

        return ProcessingResult(
            extracted_document=extracted_document,
            normalized_document=normalized_document,
            chunks=chunks,
        )
