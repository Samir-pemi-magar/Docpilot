from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_storage
from app.auth.authorization import (
    MembershipRole,
    OrganizationAccess,
    get_organization_access,
    require_organization_roles,
)
from app.db.session import get_db_session
from app.models.document import Document
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentResponse,
    DocumentVersionResponse,
)
from app.services.document import (
    create_document,
    delete_document,
    get_document,
    get_document_version,
    list_documents,
)
from app.storage.base import StorageService

router = APIRouter(
    prefix="/organizations/{organization_id}/documents",
    tags=["documents"],
)


@router.post(
    "",
    response_model=DocumentVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document_endpoint(
    organization_id: uuid.UUID,
    name: str = Form(...),
    file: UploadFile = File(...),
    access: OrganizationAccess = Depends(
        require_organization_roles(
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        )
    ),
    db: AsyncSession = Depends(get_db_session),
    storage: StorageService = Depends(get_storage),
) -> DocumentVersionResponse:
    """
    Upload a new document and create its first version.
    """

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A filename is required.",
        )

    return await create_document(
        db=db,
        storage=storage,
        organization_id=organization_id,
        user_id=access.user.id,
        name=name,
        original_filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        file=file.file,
    )


@router.get(
    "",
    response_model=list[DocumentResponse],
)
async def list_documents_endpoint(
    organization_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> list[DocumentResponse]:
    """
    List documents belonging to an organization.
    """

    return await list_documents(
        db=db,
        organization_id=organization_id,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
)
async def get_document_endpoint(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> DocumentDetailResponse:
    """
    Get a document and its versions.
    """

    document = await get_document(
        db=db,
        organization_id=organization_id,
        document_id=document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    result = await db.execute(
        select(Document)
        .options(selectinload(Document.versions))
        .where(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
    )

    return result.scalar_one()


@router.get(
    "/{document_id}/versions/{version_number}",
    response_model=DocumentVersionResponse,
)
async def get_document_version_endpoint(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    version_number: int,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> DocumentVersionResponse:
    """
    Get a specific document version.
    """

    if version_number < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Version number must be positive.",
        )

    version = await get_document_version(
        db=db,
        organization_id=organization_id,
        document_id=document_id,
        version_number=version_number,
    )

    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document version not found.",
        )

    return version


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document_endpoint(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    access: OrganizationAccess = Depends(
        require_organization_roles(
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        )
    ),
    db: AsyncSession = Depends(get_db_session),
    storage: StorageService = Depends(get_storage),
) -> None:
    """
    Delete a document and all of its versions.
    """

    deleted = await delete_document(
        db=db,
        storage=storage,
        organization_id=organization_id,
        document_id=document_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
