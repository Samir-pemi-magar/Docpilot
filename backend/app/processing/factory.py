from app.chunking.config import ChunkingConfig
from app.chunking.hybrid import HybridChunker
from app.chunking.prose import ProseChunker
from app.chunking.structured import StructuredChunker
from app.chunking.tokenizer import SimpleTokenCounter
from app.normalization.registry import NormalizerRegistry
from app.parsers.registry import ParserRegistry
from app.processing.pipeline import DocumentProcessingPipeline
from app.processing.processor import DocumentProcessor


def create_document_processor() -> DocumentProcessor:
    """Build the production document processing stack."""

    parser_registry = ParserRegistry()
    normalizer_registry = NormalizerRegistry()

    token_counter = SimpleTokenCounter()

    chunking_config = ChunkingConfig()

    prose_chunker = ProseChunker(
        config=chunking_config,
        token_counter=token_counter,
    )

    structured_chunker = StructuredChunker(
        config=chunking_config,
        token_counter=token_counter,
    )

    hybrid_chunker = HybridChunker(
        prose_chunker=prose_chunker,
        structured_chunker=structured_chunker,
    )

    pipeline = DocumentProcessingPipeline(
        parser_registry=parser_registry,
        normalizer_registry=normalizer_registry,
        chunker=hybrid_chunker,
    )

    return DocumentProcessor(pipeline=pipeline)
