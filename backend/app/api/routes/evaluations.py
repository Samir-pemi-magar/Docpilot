from __future__ import annotations

import json
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy import func, select, text
from sqlalchemy.sql import Select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authorization import OrganizationAccess, get_organization_access
from app.embeddings.base import EmbeddingProvider
from app.embeddings.dependencies import get_embedding_provider
from app.db.session import get_db_session, get_evaluation_session_factory
from app.models.document import Document
from app.models.evaluation_case import EvaluationCase
from app.models.evaluation_dataset import EvaluationDataset
from app.models.evaluation_result import EvaluationResult
from app.models.evaluation_run import EvaluationRun
from app.schemas.evaluations import (
    EvaluationCaseCreate,
    EvaluationCaseResponse,
    EvaluationCasesImportRequest,
    EvaluationCasesImportResponse,
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
    run_evaluation_background,
)
from app.services.llm import OpenAICompatibleLLMClient
from app.services.evaluation_pdf_export import generate_evaluation_report_pdf
from app.services.evaluations import (
    _case_response_data,
    create_case,
    create_dataset,
    delete_case,
    delete_cases,
    delete_dataset,
    get_case,
    get_dataset,
    import_cases,
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
    "/runs",
    response_model=list[EvaluationRunResponse],
)
async def list_evaluation_runs(
    organization_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=50),
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> list[EvaluationRun]:
    """List recent evaluation runs across this organization's datasets."""
    result = await db.execute(
        select(EvaluationRun)
        .join(
            EvaluationDataset,
            EvaluationRun.dataset_id == EvaluationDataset.id,
        )
        .where(EvaluationDataset.organization_id == organization_id)
        .order_by(
            EvaluationRun.created_at.desc(),
            EvaluationRun.id.desc(),
        )
        .limit(limit)
    )
    return list(result.scalars().all())


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


@router.post(
    "/{dataset_id}/cases/import",
    response_model=EvaluationCasesImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_evaluation_cases(
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
    payload: EvaluationCasesImportRequest,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> EvaluationCasesImportResponse:
    """Validate and atomically import JSONL evaluation cases."""
    await _require_dataset(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
    )

    lines = payload.content.splitlines()
    if len(lines) > 2000:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="A JSONL import may contain at most 2,000 lines.",
        )

    parsed: list[dict[str, object]] = []
    errors: list[str] = []
    seen_ids: dict[str, int] = {}
    document_uuids: set[uuid.UUID] = set()

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(
                f"Line {line_number}: invalid JSON ({exc.msg})."
            )
            continue

        if not isinstance(record, dict):
            errors.append(
                f"Line {line_number}: each line must contain a JSON object."
            )
            continue

        question = record.get("question")
        if not isinstance(question, str) or not question.strip():
            errors.append(
                f"Line {line_number}: 'question' must be a non-empty string."
            )
            continue
        question = question.strip()
        if len(question) > 10_000:
            errors.append(
                f"Line {line_number}: question exceeds 10,000 characters."
            )
            continue

        answer = record.get("reference_answer")
        if answer is None:
            answer = record.get("expected_answer")
        if answer is not None and not isinstance(answer, str):
            errors.append(
                f"Line {line_number}: expected answer must be a string or null."
            )
            continue
        if isinstance(answer, str) and len(answer.strip()) > 20_000:
            errors.append(
                f"Line {line_number}: reference answer exceeds 20,000 characters."
            )
            continue
        if isinstance(answer, str):
            answer = answer.strip() or None

        raw_ids = record.get("relevant_document_ids")
        if raw_ids is not None and (
            not isinstance(raw_ids, list)
            or any(not isinstance(value, str) or not value.strip()
                   for value in raw_ids)
        ):
            errors.append(
                f"Line {line_number}: relevant_document_ids must be a "
                "list of non-empty strings or null."
            )
            continue

        real_ids = []
        for value in raw_ids or []:
            try:
                document_id = uuid.UUID(value)
            except ValueError:
                # Resolve benchmark labels only when the importer supplied
                # an explicit label -> DocPilot document UUID mapping.
                document_id = payload.document_id_mapping.get(value)
                if document_id is None:
                    continue

            real_ids.append(document_id)
            document_uuids.add(document_id)

        case_id = record.get("case_id")
        if case_id is not None:
            if not isinstance(case_id, str) or not case_id.strip():
                errors.append(
                    f"Line {line_number}: case_id must be a non-empty string."
                )
                continue
            case_id = case_id.strip()
            if case_id in seen_ids:
                errors.append(
                    f"Line {line_number}: duplicate case_id {case_id!r}; "
                    f"first seen on line {seen_ids[case_id]}."
                )
                continue
            seen_ids[case_id] = line_number

        parsed.append({
            "question": question,
            "reference_answer": answer,
            "relevant_document_ids": real_ids or None,
            # Keep the full original record, including all benchmark fields.
            "metadata": record,
        })

    if not parsed and not errors:
        errors.append("The file contains no JSONL records.")

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "JSONL import rejected; no cases were imported. "
                + " ".join(errors[:20])
            ),
        )

    # Reject IDs that already exist in this dataset.
    if seen_ids:
        existing = await list_cases(db, dataset_id=dataset_id)
        existing_ids = {
            item.metadata_.get("case_id")
            for item in existing
            if isinstance(item.metadata_, dict)
            and isinstance(item.metadata_.get("case_id"), str)
        }
        duplicates = sorted(set(seen_ids) & existing_ids)
        if duplicates:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "JSONL import rejected; no cases were imported. "
                    "These case_id values already exist: "
                    + ", ".join(duplicates[:20])
                ),
            )

    # Only UUIDs are checked against organization-owned documents.
    await _validate_relevant_documents(
        db,
        organization_id=organization_id,
        document_ids=list(document_uuids),
    )

    try:
        saved = await import_cases(
            db,
            dataset_id=dataset_id,
            cases=parsed,
        )
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Import conflicted with existing dataset positions; "
                "no cases were imported."
            ),
        ) from exc

    return EvaluationCasesImportResponse(
        imported_count=len(saved),
        cases=[
            EvaluationCaseResponse(**_case_response_data(item))
            for item in saved
        ],
    )


@router.delete("/{dataset_id}/cases")
async def remove_all_evaluation_cases(
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, int]:
    """Delete all questions in one organization-scoped dataset."""
    await _require_dataset(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
    )
    deleted_count = await delete_cases(db, dataset_id=dataset_id)
    return {"deleted_count": deleted_count}


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
    background_tasks: BackgroundTasks,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
    session_factory=Depends(get_evaluation_session_factory),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    llm_client: OpenAICompatibleLLMClient = Depends(get_evaluation_llm_client),
) -> EvaluationRun:
    """Create an evaluation run and schedule its execution."""
    # Serialize evaluation starts across the application. The transaction-level
    # lock is held until commit, so simultaneous requests cannot both pass the
    # active-run check and create a run.
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": 724193681},
    )

    active_run = await db.scalar(
        select(EvaluationRun.id)
        .where(EvaluationRun.status.in_(("pending", "running")))
        .limit(1)
    )
    if active_run is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An evaluation is already running. Wait for it to finish before starting another.",
        )

    dataset = await _require_dataset(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
    )

    total_cases = await db.scalar(
        select(func.count())
        .select_from(EvaluationCase)
        .where(EvaluationCase.dataset_id == dataset.id)
    )

    run = EvaluationRun(
        dataset_id=dataset.id,
        started_by_user_id=access.user.id,
        status="pending",
        total_cases=total_cases or 0,
        completed_cases=0,
        failed_cases=0,
        metrics={},
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    background_tasks.add_task(
        run_evaluation_background,
        session_factory=session_factory,
        run_id=run.id,
        dataset_id=dataset.id,
        user_id=access.user.id,
        embedding_provider=embedding_provider,
        llm_client=llm_client,
        top_k=payload.top_k,
    )

    return run


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



@router.get("/{dataset_id}/runs/{run_id}/pdf")
async def download_evaluation_report_pdf(
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
    run_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """Download a PDF report for a persisted evaluation run."""
    dataset = await _require_dataset(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
    )
    run = await _require_evaluation_run(
        db,
        organization_id=organization_id,
        dataset_id=dataset_id,
        run_id=run_id,
    )

    result = await db.execute(
        select(EvaluationResult)
        .where(EvaluationResult.run_id == run.id)
        .order_by(EvaluationResult.created_at, EvaluationResult.id)
    )
    all_results = list(result.scalars().all())

    pdf_bytes = generate_evaluation_report_pdf(
        dataset_name=dataset.name,
        run=run,
        results=all_results,
    )

    filename = f"docpilot-evaluation-{run.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
