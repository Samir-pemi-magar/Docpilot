from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authorization import (
    MembershipRole,
    OrganizationAccess,
    get_organization_access,
    require_membership_management,
    require_organization_roles,
    validate_membership_role_assignment,
)
from app.auth.dependencies import get_current_user
from app.api.dependencies import get_storage
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.membership import (
    MembershipCreate,
    MembershipUpdate,
    OrganizationMemberResponse,
)
from app.storage.base import StorageService
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)
from app.services.membership import (
    add_organization_member,
    get_membership,
    list_organization_members,
    remove_membership,
    update_membership_role,
)
from app.services.organization import (
    create_organization,
    get_organization,
    list_user_organizations,
    update_organization,
    delete_organization,
)

router = APIRouter(
    prefix="/organizations",
    tags=["organizations"],
)


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization_endpoint(
    data: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    try:
        return await create_organization(
            db=db,
            name=data.name,
            slug=data.slug,
            owner_user_id=current_user.id,
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization with this slug already exists.",
        )


@router.get(
    "",
    response_model=list[OrganizationResponse],
)
async def list_organizations_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[OrganizationResponse]:
    return await list_user_organizations(
        db=db,
        user_id=current_user.id,
    )


@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
)
async def get_organization_endpoint(
    organization_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    organization = await get_organization(
        db=db,
        organization_id=organization_id,
    )

    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    return organization


@router.patch(
    "/{organization_id}",
    response_model=OrganizationResponse,
)
async def update_organization_endpoint(
    organization_id: uuid.UUID,
    data: OrganizationUpdate,
    access: OrganizationAccess = Depends(
        require_organization_roles(
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        )
    ),
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    organization = await get_organization(
        db=db,
        organization_id=organization_id,
    )

    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    try:
        return await update_organization(
            db=db,
            organization=organization,
            name=data.name,
            slug=data.slug,
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization with this slug already exists.",
        )


@router.get(
    "/{organization_id}/members",
    response_model=list[OrganizationMemberResponse],
)
async def list_members_endpoint(
    organization_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> list[OrganizationMemberResponse]:
    memberships = await list_organization_members(
        db=db,
        organization_id=organization_id,
    )

    return [
        OrganizationMemberResponse(
            membership_id=membership.id,
            user_id=membership.user_id,
            email=membership.user.email,
            full_name=membership.user.full_name,
            role=membership.role,
            joined_at=membership.created_at,
        )
        for membership in memberships
    ]


@router.post(
    "/{organization_id}/members",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member_endpoint(
    organization_id: uuid.UUID,
    data: MembershipCreate,
    access: OrganizationAccess = Depends(
        require_organization_roles(
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        )
    ),
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationMemberResponse:
    validate_membership_role_assignment(data.role)

    try:
        membership = await add_organization_member(
            db=db,
            organization_id=organization_id,
            email=str(data.email),
            role=data.role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email does not exist.",
        )

    return OrganizationMemberResponse(
        membership_id=membership.id,
        user_id=membership.user_id,
        email=membership.user.email,
        full_name=membership.user.full_name,
        role=membership.role,
        joined_at=membership.created_at,
    )


@router.patch(
    "/{organization_id}/members/{membership_id}",
    response_model=OrganizationMemberResponse,
)
async def update_member_endpoint(
    organization_id: uuid.UUID,
    membership_id: uuid.UUID,
    data: MembershipUpdate,
    access: OrganizationAccess = Depends(
        require_organization_roles(
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        )
    ),
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationMemberResponse:
    membership = await get_membership(
        db=db,
        organization_id=organization_id,
        membership_id=membership_id,
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found.",
        )

    require_membership_management(
        access=access,
        target_role=membership.role,
    )

    try:
        membership = await update_membership_role(
            db=db,
            membership=membership,
            role=data.role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return OrganizationMemberResponse(
        membership_id=membership.id,
        user_id=membership.user_id,
        email=membership.user.email,
        full_name=membership.user.full_name,
        role=membership.role,
        joined_at=membership.created_at,
    )


@router.delete(
    "/{organization_id}/members/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member_endpoint(
    organization_id: uuid.UUID,
    membership_id: uuid.UUID,
    access: OrganizationAccess = Depends(
        require_organization_roles(
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        )
    ),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    membership = await get_membership(
        db=db,
        organization_id=organization_id,
        membership_id=membership_id,
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found.",
        )

    require_membership_management(
        access=access,
        target_role=membership.role,
    )

    try:
        await remove_membership(
            db=db,
            membership=membership,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )



@router.delete(
    "/{organization_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_organization_endpoint(
    organization_id: uuid.UUID,
    access: OrganizationAccess = Depends(
        require_organization_roles(MembershipRole.OWNER)
    ),
    db: AsyncSession = Depends(get_db_session),
    storage: StorageService = Depends(get_storage),
) -> None:
    organization = await get_organization(
        db=db,
        organization_id=organization_id,
    )

    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    await delete_organization(
        db=db,
        organization=organization,
        storage=storage,
    )
