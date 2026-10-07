from abc import ABC, abstractmethod


class TokenCounter(ABC):
    """Interface for tokenizing and counting text."""

    @abstractmethod
    def count(self, text: str) -> int:
        """Return the number of tokens in the supplied text."""
        raise NotImplementedError

    @abstractmethod
    def take_first(self, text: str, count: int) -> str:
        """Return the first `count` tokens from the supplied text."""
        raise NotImplementedError

    @abstractmethod
    def take_last(self, text: str, count: int) -> str:
        """Return the last `count` tokens from the supplied text."""
        raise NotImplementedError

    @abstractmethod
    def split(self, text: str, max_tokens: int) -> list[str]:
        """Split text into pieces containing at most `max_tokens` tokens."""
        raise NotImplementedError


class SimpleTokenCounter(TokenCounter):
    """Simple whitespace-based token counter for testing and development."""

    def count(self, text: str) -> int:
        return len(text.split())

    def take_first(self, text: str, count: int) -> str:
        if count <= 0:
            return ""

        tokens = text.split()

        return " ".join(tokens[:count])

    def take_last(self, text: str, count: int) -> str:
        if count <= 0:
            return ""

        tokens = text.split()

        return " ".join(tokens[-count:])

    def split(self, text: str, max_tokens: int) -> list[str]:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be greater than 0")

        tokens = text.split()

        return [
            " ".join(tokens[index:index + max_tokens])
            for index in range(0, len(tokens), max_tokens)
        ]
