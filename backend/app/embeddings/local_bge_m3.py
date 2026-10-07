from collections.abc import Sequence

from FlagEmbedding import BGEM3FlagModel

from app.embeddings.base import EmbeddingProvider
from app.embeddings.models import BatchEmbeddingResult, EmbeddingResult


class LocalBGEEmbeddingProvider(EmbeddingProvider):
    """Generate embeddings locally with BAAI/bge-m3."""

    MODEL_NAME = "BAAI/bge-m3"
    DIMENSION = 1024

    def __init__(
        self,
        *,
        device: str | None = None,
        use_fp16: bool = False,
        max_length: int = 1024,
    ) -> None:
        self.model = BGEM3FlagModel(
            self.MODEL_NAME,
            use_fp16=use_fp16,
            device=device,
        )
        self.max_length = max_length

    def embed_query(self, text: str) -> EmbeddingResult:
        if not text.strip():
            raise ValueError("Cannot embed empty query text.")

        output = self.model.encode(
            [text],
            batch_size=1,
            max_length=self.max_length,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )

        vector = output["dense_vecs"][0].tolist()

        return EmbeddingResult(
            vector=[float(value) for value in vector],
            model=self.MODEL_NAME,
            dimension=self.DIMENSION,
        )

    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> BatchEmbeddingResult:
        if not texts:
            return BatchEmbeddingResult(embeddings=[])

        if any(not text.strip() for text in texts):
            raise ValueError("Document texts must not contain empty strings.")

        output = self.model.encode(
            list(texts),
            batch_size=min(8, len(texts)),
            max_length=self.max_length,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )

        embeddings = [
            EmbeddingResult(
                vector=[float(value) for value in vector.tolist()],
                model=self.MODEL_NAME,
                dimension=self.DIMENSION,
            )
            for vector in output["dense_vecs"]
        ]

        return BatchEmbeddingResult(embeddings=embeddings)
