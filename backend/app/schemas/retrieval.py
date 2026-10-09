from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchRequest(BaseModel):
    """Input for searching an organization's indexed documents."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=10_000)
    top_k: int = Field(default=5, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        if not value:
            raise ValueError("Query must not be empty.")
        return value


class SearchResultItem(BaseModel):
    """A chunk returned by semantic search."""

    chunk_id: uuid.UUID
    document_version_id: uuid.UUID
    chunk_index: int
    text: str
    distance: float
    model: str


class SearchResponse(BaseModel):
    """Semantic search results for an organization."""

    query: str
    results: list[SearchResultItem]
