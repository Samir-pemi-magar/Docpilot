from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    """A question about documents belonging to one organization."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=10_000)
    top_k: int = Field(default=5, ge=1, le=10)
    conversation_id: uuid.UUID | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        if not value:
            raise ValueError("Question must not be empty.")
        return value


class ChatSource(BaseModel):
    """A retrieved document chunk used as answer context."""

    chunk_id: uuid.UUID
    document_version_id: uuid.UUID
    chunk_index: int
    text: str
    distance: float
    document_id: uuid.UUID | None = None
    document_name: str = "Document"


class ChatTraceStep(BaseModel):
    """A measured, user-safe step in processing a chat request."""

    id: str
    type: str
    tool: str
    label: str
    detail: str
    duration: int = Field(ge=0)
    timestamp: str
    result: str
    status: str = "success"


class ChatResponse(BaseModel):
    """An answer, its conversation ID, sources, and execution trace."""

    conversation_id: uuid.UUID
    query: str
    answer: str
    sources: list[ChatSource]
    trace: list[ChatTraceStep] = Field(default_factory=list)
