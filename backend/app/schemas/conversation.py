from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationSummary(BaseModel):
    """A conversation entry returned by the list endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class ConversationListResponse(BaseModel):
    """Paginated list of conversations owned by the authenticated user."""

    items: list[ConversationSummary]
    total: int
    limit: int
    offset: int


class ConversationMessageResponse(BaseModel):
    """A persisted message returned when reading conversation history."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    sources: list[dict] | None
    created_at: datetime


class ConversationDetailResponse(ConversationSummary):
    """Conversation metadata together with its ordered messages."""

    messages: list[ConversationMessageResponse]
