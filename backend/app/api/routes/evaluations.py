from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.sql import Select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authorization import OrganizationAccess, get_organization_access
from app.embeddings.base import EmbeddingProvider
from app.embeddings.dependencies import get_embedding_provider
from app.db.session import get_db_session
from app.models.document import Document
from app.models.evaluation_dataset import EvaluationDataset
from app.models.evaluation_result import EvaluationResult
from app.models.evaluation_run import EvaluationRun
from app.schemas.evaluations import (
    EvaluationCaseCreate,
    EvaluationCaseResponse,
    EvaluationCaseUpdate,
    EvaluationDatasetCreate,
    EvaluationDatasetResponse,
    EvaluationDatasetUpdate,
    EvaluationResultResponse,
    EvaluationRunCreate,
    EvaluationRunResponse,
)
from app.services.evaluation_runner import (
    get_evaluation_llm_client,
    run_evaluation,
)
from app.services.llm import OpenAICompatibleLLMClient
from app.services.evaluations import (
    _case_response_data,
    create_case,
    create_dataset,
    delete_case,
    delete_dataset,
    get_case,
    get_dataset,
    list_cases,
    list_datasets,
    update_case,
    update_dataset,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/evaluation-datasets",
    tags=["evaluations"],
)


async def _validate_relevant_documents(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    document_ids: list[uuid.UUID] | None,
) -> None:
    """Reject document references that do not belong to this organization."""
    if document_ids is None:
        return

    requested_ids = set(document_ids)
    if not requested_ids:
        return

    result = await db.execute(
        select(Document.id).where(
            Document.organization_id == organization_id,
            Document.id.in_(requested_ids),
        )
    )
    found_ids = set(result.scalars().all())

    if found_ids != requested_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Every relevant document ID must identify a document "
                "belonging to this organization."
            ),
        )


async def _require_dataset(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
) -> EvaluationDataset:
    dataset = await get_dataset(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
    )
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation dataset not found.",
        )
    return dataset


@router.post(
    "",
    response_model=EvaluationDatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation_dataset(
    organization_id: uuid.UUID,
    payload: EvaluationDatasetCreate,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> EvaluationDataset:
    return await create_dataset(
        db,
        organization_id=organization_id,
        user_id=access.user.id,
        name=payload.name,
        description=payload.description,
    )


@router.get(
    "",
    response_model=list[EvaluationDatasetResponse],
)
async def get_evaluation_datasets(
    organization_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> list[EvaluationDataset]:
    return await list_datasets(
        db,
        organization_id=organization_id,
    )


@router.get(
    "/{dataset_id}",
    response_model=EvaluationDatasetResponse,
)
async def get_evaluation_dataset(
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> EvaluationDataset:
    return await _require_dataset(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
    )


@router.patch(
    "/{dataset_id}",
    response_model=EvaluationDatasetResponse,
)
async def patch_evaluation_dataset(
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
    payload: EvaluationDatasetUpdate,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> EvaluationDataset:
    dataset = await _require_dataset(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
    )
    changes = payload.model_dump(exclude_unset=True)
    return await update_dataset(db, dataset=dataset, changes=changes)


@router.delete(
    "/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_evaluation_dataset(
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    dataset = await _require_dataset(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
    )
    await delete_dataset(db, dataset=dataset)


@router.post(
    "/{dataset_id}/cases",
    response_model=EvaluationCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation_case(
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
    payload: EvaluationCaseCreate,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> EvaluationCaseResponse:
    await _require_dataset(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
    )
    await _validate_relevant_documents(
        db,
        organization_id=organization_id,
        document_ids=payload.relevant_document_ids,
    )

    try:
        case = await create_case(
            db,
            dataset_id=dataset_id,
            question=payload.question,
            reference_answer=payload.reference_answer,
            relevant_document_ids=payload.relevant_document_ids,
            metadata=payload.metadata,
            position=payload.position,
        )
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That case position is already in use in this dataset.",
        ) from exc

    return EvaluationCaseResponse(**_case_response_data(case))


@router.get(
    "/{dataset_id}/cases",
    response_model=list[EvaluationCaseResponse],
)
async def get_evaluation_cases(
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> list[EvaluationCaseResponse]:
    await _require_dataset(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
    )
    cases = await list_cases(db, dataset_id=dataset_id)
    return [
        EvaluationCaseResponse(**_case_response_data(case))
        for case in cases
    ]


@router.patch(
    "/{dataset_id}/cases/{case_id}",
    response_model=EvaluationCaseResponse,
)
async def patch_evaluation_case(
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
    case_id: uuid.UUID,
    payload: EvaluationCaseUpdate,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> EvaluationCaseResponse:
    case = await get_case(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
        case_id=case_id,
    )
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation case not found.",
        )

    changes = payload.model_dump(exclude_unset=True)
    if "relevant_document_ids" in changes:
        await _validate_relevant_documents(
            db,
            organization_id=organization_id,
            document_ids=changes["relevant_document_ids"],
        )

    try:
        case = await update_case(db, case=case, changes=changes)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That case position is already in use in this dataset.",
        ) from exc

    return EvaluationCaseResponse(**_case_response_data(case))


@router.delete(
    "/{dataset_id}/cases/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_evaluation_case(
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
    case_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    case = await get_case(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
        case_id=case_id,
    )
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation case not found.",
        )
    await delete_case(db, case=case)



async def _require_evaluation_run(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
    run_id: uuid.UUID,
) -> EvaluationRun:
    """Find a run only through its organization-scoped dataset."""
    result = await db.execute(
        select(EvaluationRun)
        .join(
            EvaluationDataset,
            EvaluationRun.dataset_id == EvaluationDataset.id,
        )
        .where(
            EvaluationRun.id == run_id,
            EvaluationRun.dataset_id == dataset_id,
            EvaluationDataset.organization_id == organization_id,
        )
    )
    run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found.",
        )

    return run


@router.post(
    "/{dataset_id}/runs",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_evaluation_run(
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
    payload: EvaluationRunCreate,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    llm_client: OpenAICompatibleLLMClient = Depends(get_evaluation_llm_client),
) -> EvaluationRun:
    """Execute an evaluation dataset and return its persisted run."""
    dataset = await _require_dataset(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
    )

    return await run_evaluation(
        db,
        dataset=dataset,
        user_id=access.user.id,
        embedding_provider=embedding_provider,
        llm_client=llm_client,
        top_k=payload.top_k,
    )


@router.get(
    "/{dataset_id}/runs/{run_id}",
    response_model=EvaluationRunResponse,
)
async def get_evaluation_run(
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
    run_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> EvaluationRun:
    """Return a run belonging to the specified organization and dataset."""
    await _require_dataset(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
    )
    return await _require_evaluation_run(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
        run_id=run_id,
    )


@router.get(
    "/{dataset_id}/runs/{run_id}/results",
    response_model=list[EvaluationResultResponse],
)
async def get_evaluation_run_results(
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
    run_id: uuid.UUID,
    include_failures: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> list[EvaluationResult]:
    """List persisted case results with pagination and optional filtering."""
    await _require_dataset(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
    )
    await _require_evaluation_run(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
        run_id=run_id,
    )

    query: Select[tuple[EvaluationResult]] = (
        select(EvaluationResult)
        .where(EvaluationResult.run_id == run_id)
        .order_by(EvaluationResult.created_at, EvaluationResult.id)
    )

    if not include_failures:
        query = query.where(EvaluationResult.status == "completed")

    result = await db.execute(query.limit(limit).offset(offset))
    return list(result.scalars().all())
