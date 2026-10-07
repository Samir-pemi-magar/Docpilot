from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkingConfig:
    """Configuration controlling document chunking behavior."""

    target_tokens: int = 500
    max_tokens: int = 800
    overlap_tokens: int = 75

    def __post_init__(self) -> None:
        if self.target_tokens <= 0:
            raise ValueError("target_tokens must be greater than 0")

        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be greater than 0")

        if self.overlap_tokens < 0:
            raise ValueError("overlap_tokens cannot be negative")

        if self.target_tokens > self.max_tokens:
            raise ValueError(
                "target_tokens cannot be greater than max_tokens"
            )

        if self.overlap_tokens >= self.max_tokens:
            raise ValueError(
                "overlap_tokens must be smaller than max_tokens"
            )