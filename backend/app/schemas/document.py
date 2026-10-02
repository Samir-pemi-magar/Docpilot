from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_number: int
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_user_id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime


class DocumentDetailResponse(DocumentResponse):
    versions: list[DocumentVersionResponse]
