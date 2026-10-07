from typing import BinaryIO

from app.processing.models import ProcessingResult
from app.processing.pipeline import DocumentProcessingPipeline


class DocumentProcessor:
    """High-level entry point for document processing."""

    def __init__(
        self,
        pipeline: DocumentProcessingPipeline,
    ) -> None:
        self.pipeline = pipeline

    def process(
        self,
        filename: str,
        file: BinaryIO,
    ) -> ProcessingResult:
        """Process a document end to end."""

        return self.pipeline.process(filename, file)
