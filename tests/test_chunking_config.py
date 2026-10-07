import pytest

from app.chunking.config import ChunkingConfig


def test_chunking_config_defaults() -> None:
    config = ChunkingConfig()

    assert config.target_tokens == 500
    assert config.max_tokens == 800
    assert config.overlap_tokens == 75


def test_chunking_config_accepts_custom_values() -> None:
    config = ChunkingConfig(
        target_tokens=400,
        max_tokens=600,
        overlap_tokens=50,
    )

    assert config.target_tokens == 400
    assert config.max_tokens == 600
    assert config.overlap_tokens == 50


def test_target_tokens_cannot_exceed_max_tokens() -> None:
    with pytest.raises(ValueError, match="target_tokens"):
        ChunkingConfig(
            target_tokens=900,
            max_tokens=800,
        )


def test_overlap_cannot_be_negative() -> None:
    with pytest.raises(ValueError, match="overlap_tokens"):
        ChunkingConfig(overlap_tokens=-1)


def test_overlap_must_be_smaller_than_max_tokens() -> None:
    with pytest.raises(ValueError, match="overlap_tokens"):
        ChunkingConfig(
            target_tokens=50,
            max_tokens=100,
            overlap_tokens=100,
        )


def test_config_is_immutable() -> None:
    config = ChunkingConfig()

    with pytest.raises(AttributeError):
        config.target_tokens = 600