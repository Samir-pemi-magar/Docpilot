from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.membership import Membership
from app.models.user import User


class MembershipRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


@dataclass(frozen=True)
class OrganizationAccess:
    user: User
    membership: Membership


async def get_organization_access(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationAccess:
    """Require the current user to belong to the requested organization."""
    result = await db.execute(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == current_user.id,
        )
    )

    membership = result.scalar_one_or_none()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this organization.",
        )

    return OrganizationAccess(
        user=current_user,
        membership=membership,
    )


def require_organization_roles(
    *allowed_roles: MembershipRole,
):
    """Create a dependency requiring one of the specified organization roles."""

    async def dependency(
        access: OrganizationAccess = Depends(get_organization_access),
    ) -> OrganizationAccess:
        if access.membership.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return access

    return dependency


def can_manage_memberships(
    actor_role: MembershipRole,
    target_role: MembershipRole,
) -> bool:
    """Return whether an actor may modify the target membership."""
    if actor_role == MembershipRole.OWNER:
        return True

    if actor_role == MembershipRole.ADMIN:
        return target_role == MembershipRole.MEMBER

    return False


def require_membership_management(
    access: OrganizationAccess,
    target_role: MembershipRole,
) -> None:
    """Enforce membership-management permissions."""
    if not can_manage_memberships(
        actor_role=access.membership.role,
        target_role=target_role,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins can only manage members.",
        )


def validate_membership_role_assignment(
    role: MembershipRole,
) -> None:
    """Prevent ownership from being assigned through generic membership APIs."""
    if role == MembershipRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owner role cannot be assigned through this endpoint.",
        )
