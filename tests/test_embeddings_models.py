import pytest

from app.embeddings.models import BatchEmbeddingResult, EmbeddingResult


def test_embedding_result_validates_vector_dimension() -> None:
    result = EmbeddingResult(
        vector=[0.1, 0.2, 0.3],
        model="test-model",
        dimension=3,
    )

    assert result.vector == [0.1, 0.2, 0.3]
    assert result.model == "test-model"
    assert result.dimension == 3


def test_embedding_result_rejects_wrong_dimension() -> None:
    with pytest.raises(ValueError, match="vector length"):
        EmbeddingResult(
            vector=[0.1, 0.2],
            model="test-model",
            dimension=3,
        )


def test_embedding_result_rejects_empty_model() -> None:
    with pytest.raises(ValueError, match="model name"):
        EmbeddingResult(
            vector=[0.1, 0.2],
            model="",
            dimension=2,
        )


def test_embedding_result_rejects_non_positive_dimension() -> None:
    with pytest.raises(ValueError, match="dimension"):
        EmbeddingResult(
            vector=[],
            model="test-model",
            dimension=0,
        )


def test_batch_embedding_result_exposes_model_and_dimension() -> None:
    result = BatchEmbeddingResult(
        embeddings=[
            EmbeddingResult(
                vector=[0.1, 0.2],
                model="test-model",
                dimension=2,
            ),
            EmbeddingResult(
                vector=[0.3, 0.4],
                model="test-model",
                dimension=2,
            ),
        ]
    )

    assert result.model == "test-model"
    assert result.dimension == 2


def test_empty_batch_has_no_model_or_dimension() -> None:
    result = BatchEmbeddingResult(embeddings=[])

    assert result.model is None
    assert result.dimension is None
