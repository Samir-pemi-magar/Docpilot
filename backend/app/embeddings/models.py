from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingResult:
    """The result of embedding a single piece of text."""

    vector: list[float]
    model: str
    dimension: int

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("Embedding model name must not be empty.")

        if self.dimension <= 0:
            raise ValueError("Embedding dimension must be positive.")

        if len(self.vector) != self.dimension:
            raise ValueError(
                "Embedding vector length must match the declared dimension."
            )


@dataclass(frozen=True)
class BatchEmbeddingResult:
    """The results of embedding multiple pieces of text."""

    embeddings: list[EmbeddingResult]

    @property
    def dimension(self) -> int | None:
        """Return the embedding dimension, or None for an empty batch."""
        if not self.embeddings:
            return None

        return self.embeddings[0].dimension

    @property
    def model(self) -> str | None:
        """Return the model name, or None for an empty batch."""
        if not self.embeddings:
            return None

        return self.embeddings[0].model
