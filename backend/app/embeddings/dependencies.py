from __future__ import annotations

from functools import lru_cache
from typing import cast

from fastapi import Request

from app.embeddings.base import EmbeddingProvider
from app.embeddings.local_bge_m3 import LocalBGEEmbeddingProvider


@lru_cache(maxsize=1)
def get_default_embedding_provider() -> EmbeddingProvider:
    """Create and cache the default local embedding provider."""
    return LocalBGEEmbeddingProvider()


def get_embedding_provider(request: Request) -> EmbeddingProvider:
    """Return the app-configured provider, creating the default lazily."""
    provider = getattr(request.app.state, "embedding_provider", None)

    if provider is None:
        provider = get_default_embedding_provider()
        request.app.state.embedding_provider = provider

    return cast(EmbeddingProvider, provider)
