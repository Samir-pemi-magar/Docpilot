from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation_case import EvaluationCase
from app.models.evaluation_dataset import EvaluationDataset


def _case_response_data(case: EvaluationCase) -> dict[str, Any]:
    """Convert database JSON UUID strings to the public response shape."""
    return {
        "id": case.id,
        "dataset_id": case.dataset_id,
        "position": case.position,
        "question": case.question,
        "reference_answer": case.reference_answer,
        "relevant_document_ids": (
            [uuid.UUID(value) for value in case.relevant_document_ids]
            if case.relevant_document_ids is not None
            else None
        ),
        "metadata": case.metadata_,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
    }


async def create_dataset(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    description: str | None,
) -> EvaluationDataset:
    dataset = EvaluationDataset(
        organization_id=organization_id,
        created_by_user_id=user_id,
        name=name,
        description=description,
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


async def list_datasets(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
) -> list[EvaluationDataset]:
    result = await db.execute(
        select(EvaluationDataset)
        .where(EvaluationDataset.organization_id == organization_id)
        .order_by(EvaluationDataset.created_at.desc(), EvaluationDataset.id)
    )
    return list(result.scalars().all())


async def get_dataset(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
) -> EvaluationDataset | None:
    result = await db.execute(
        select(EvaluationDataset).where(
            EvaluationDataset.id == dataset_id,
            EvaluationDataset.organization_id == organization_id,
        )
    )
    return result.scalar_one_or_none()


async def update_dataset(
    db: AsyncSession,
    *,
    dataset: EvaluationDataset,
    changes: dict[str, Any],
) -> EvaluationDataset:
    for field, value in changes.items():
        setattr(dataset, field, value)
    await db.commit()
    await db.refresh(dataset)
    return dataset


async def delete_dataset(
    db: AsyncSession,
    *,
    dataset: EvaluationDataset,
) -> None:
    await db.delete(dataset)
    await db.commit()


async def list_cases(
    db: AsyncSession,
    *,
    dataset_id: uuid.UUID,
) -> list[EvaluationCase]:
    result = await db.execute(
        select(EvaluationCase)
        .where(EvaluationCase.dataset_id == dataset_id)
        .order_by(EvaluationCase.position, EvaluationCase.created_at, EvaluationCase.id)
    )
    return list(result.scalars().all())


async def create_case(
    db: AsyncSession,
    *,
    dataset_id: uuid.UUID,
    question: str,
    reference_answer: str | None,
    relevant_document_ids: list[uuid.UUID] | None,
    metadata: dict[str, Any],
    position: int | None,
) -> EvaluationCase:
    if position is None:
        result = await db.execute(
            select(func.max(EvaluationCase.position)).where(
                EvaluationCase.dataset_id == dataset_id
            )
        )
        max_position = result.scalar_one_or_none()
        position = 0 if max_position is None else max_position + 1

    case = EvaluationCase(
        dataset_id=dataset_id,
        position=position,
        question=question,
        reference_answer=reference_answer,
        relevant_document_ids=(
            [str(value) for value in relevant_document_ids]
            if relevant_document_ids is not None
            else None
        ),
        metadata_=metadata,
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case


async def get_case(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
    case_id: uuid.UUID,
) -> EvaluationCase | None:
    result = await db.execute(
        select(EvaluationCase)
        .join(
            EvaluationDataset,
            EvaluationDataset.id == EvaluationCase.dataset_id,
        )
        .where(
            EvaluationCase.id == case_id,
            EvaluationCase.dataset_id == dataset_id,
            EvaluationDataset.organization_id == organization_id,
        )
    )
    return result.scalar_one_or_none()


async def update_case(
    db: AsyncSession,
    *,
    case: EvaluationCase,
    changes: dict[str, Any],
) -> EvaluationCase:
    for field, value in changes.items():
        if field == "relevant_document_ids":
            value = [str(item) for item in value] if value is not None else None
        elif field == "metadata":
            field = "metadata_"
        setattr(case, field, value)

    await db.commit()
    await db.refresh(case)
    return case


async def delete_case(
    db: AsyncSession,
    *,
    case: EvaluationCase,
) -> None:
    await db.delete(case)
    await db.commit()
