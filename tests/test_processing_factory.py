from app.chunking.hybrid import HybridChunker
from app.processing.factory import create_document_processor
from app.processing.processor import DocumentProcessor


def test_create_document_processor_builds_production_stack() -> None:
    processor = create_document_processor()

    assert isinstance(processor, DocumentProcessor)

    pipeline = processor.pipeline

    assert isinstance(pipeline.chunker, HybridChunker)
