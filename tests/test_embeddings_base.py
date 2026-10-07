from collections.abc import Sequence

from app.embeddings.base import EmbeddingProvider
from app.embeddings.models import BatchEmbeddingResult, EmbeddingResult


class FakeEmbeddingProvider(EmbeddingProvider):
    """Small deterministic provider used only for testing the interface."""

    def embed_query(self, text: str) -> EmbeddingResult:
        return EmbeddingResult(
            vector=[float(len(text))],
            model="fake-model",
            dimension=1,
        )

    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> BatchEmbeddingResult:
        return BatchEmbeddingResult(
            embeddings=[
                EmbeddingResult(
                    vector=[float(len(text))],
                    model="fake-model",
                    dimension=1,
                )
                for text in texts
            ]
        )


def test_embedding_provider_supports_query_embedding() -> None:
    provider = FakeEmbeddingProvider()

    result = provider.embed_query("hello")

    assert result.model == "fake-model"
    assert result.dimension == 1
    assert result.vector == [5.0]


def test_embedding_provider_supports_batch_document_embedding() -> None:
    provider = FakeEmbeddingProvider()

    result = provider.embed_documents(
        [
            "hello",
            "hello world",
            "document text",
        ]
    )

    assert len(result.embeddings) == 3
    assert result.model == "fake-model"
    assert result.dimension == 1
    assert [embedding.vector for embedding in result.embeddings] == [
        [5.0],
        [11.0],
        [13.0],
    ]


def test_embedding_provider_accepts_tuples() -> None:
    provider = FakeEmbeddingProvider()

    result = provider.embed_documents(
        (
            "first",
            "second",
        )
    )

    assert len(result.embeddings) == 2
    assert result.embeddings[0].vector == [5.0]
    assert result.embeddings[1].vector == [6.0]
