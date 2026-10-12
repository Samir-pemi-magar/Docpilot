from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvaluationDatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Dataset name cannot be blank.")
        return value


class EvaluationDatasetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Dataset name cannot be blank.")
        return value


class EvaluationDatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_user_id: uuid.UUID | None
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class EvaluationCaseCreate(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)
    reference_answer: str | None = Field(default=None, max_length=20_000)
    relevant_document_ids: list[uuid.UUID] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    position: int | None = Field(default=None, ge=0)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Evaluation question cannot be blank.")
        return value

    @field_validator("reference_answer")
    @classmethod
    def validate_reference_answer(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class EvaluationCaseUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=1, max_length=10_000)
    reference_answer: str | None = Field(default=None, max_length=20_000)
    relevant_document_ids: list[uuid.UUID] | None = None
    metadata: dict[str, Any] | None = None
    position: int | None = Field(default=None, ge=0)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Evaluation question cannot be blank.")
        return value

    @field_validator("reference_answer")
    @classmethod
    def validate_reference_answer(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class EvaluationCaseResponse(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    position: int
    question: str
    reference_answer: str | None
    relevant_document_ids: list[uuid.UUID] | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class EvaluationCasesImportRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5_000_000)


class EvaluationCasesImportResponse(BaseModel):
    imported_count: int
    cases: list[EvaluationCaseResponse]


class EvaluationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    started_by_user_id: uuid.UUID | None
    status: str
    total_cases: int
    completed_cases: int
    failed_cases: int
    metrics: dict[str, Any]
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class EvaluationResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    case_id: uuid.UUID | None
    question_snapshot: str
    reference_answer_snapshot: str | None
    case_metadata_snapshot: dict[str, Any]
    actual_answer: str | None
    retrieved_sources: list[dict[str, Any]]
    metrics: dict[str, Any]
    status: str
    error_message: str | None
    duration_ms: int | None
    created_at: datetime


class EvaluationRunCreate(BaseModel):
    """Options for starting an evaluation run."""

    top_k: int = Field(default=5, ge=1, le=100)
