from typing import Protocol

from app.chunking.models import Chunk
from app.normalization.models import NormalizedDocument


class Chunker(Protocol):
    """Interface implemented by document chunkers."""

    def chunk(self, document: NormalizedDocument) -> list[Chunk]:
        """Create chunks from a normalized document."""
        ...
