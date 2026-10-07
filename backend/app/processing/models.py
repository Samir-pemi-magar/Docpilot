from dataclasses import dataclass, field

from app.chunking.models import Chunk
from app.normalization.models import NormalizedDocument
from app.parsers.models import ExtractedDocument


@dataclass
class ProcessingResult:
    """Result produced by the document processing pipeline."""

    extracted_document: ExtractedDocument
    normalized_document: NormalizedDocument
    chunks: list[Chunk] = field(default_factory=list)
