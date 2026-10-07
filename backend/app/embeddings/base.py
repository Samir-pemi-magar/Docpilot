from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.embeddings.models import BatchEmbeddingResult, EmbeddingResult


class EmbeddingProvider(ABC):
    """Interface for generating embeddings."""

    @abstractmethod
    def embed_query(self, text: str) -> EmbeddingResult:
        """Generate an embedding for a user query."""
        raise NotImplementedError

    @abstractmethod
    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> BatchEmbeddingResult:
        """Generate embeddings for document texts."""
        raise NotImplementedError
