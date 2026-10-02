from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.authorization import MembershipRole
from app.models.membership import Membership
from app.models.user import User


async def list_organization_members(
    db: AsyncSession,
    organization_id: uuid.UUID,
) -> list[Membership]:
    result = await db.execute(
        select(Membership)
        .options(selectinload(Membership.user))
        .where(
            Membership.organization_id == organization_id,
        )
        .order_by(Membership.created_at)
    )

    return list(result.scalars().all())


async def get_membership(
    db: AsyncSession,
    organization_id: uuid.UUID,
    membership_id: uuid.UUID,
) -> Membership | None:
    result = await db.execute(
        select(Membership)
        .options(selectinload(Membership.user))
        .where(
            Membership.id == membership_id,
            Membership.organization_id == organization_id,
        )
    )

    return result.scalar_one_or_none()


async def add_organization_member(
    db: AsyncSession,
    organization_id: uuid.UUID,
    email: str,
    role: MembershipRole,
) -> Membership | None:
    user_result = await db.execute(
        select(User).where(User.email == email)
    )
    user = user_result.scalar_one_or_none()

    if user is None:
        return None

    existing_result = await db.execute(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user.id,
        )
    )

    existing_membership = existing_result.scalar_one_or_none()

    if existing_membership is not None:
        raise ValueError("User is already a member of this organization.")

    membership = Membership(
        organization_id=organization_id,
        user_id=user.id,
        role=role.value,
    )

    db.add(membership)
    await db.commit()

    result = await db.execute(
        select(Membership)
        .options(selectinload(Membership.user))
        .where(Membership.id == membership.id)
    )

    return result.scalar_one()


async def update_membership_role(
    db: AsyncSession,
    membership: Membership,
    role: MembershipRole,
) -> Membership:
    if membership.role == MembershipRole.OWNER:
        raise ValueError("Owner membership cannot be modified through this endpoint.")

    if role == MembershipRole.OWNER:
        raise ValueError("Owner role cannot be assigned through this endpoint.")

    membership.role = role.value

    await db.commit()

    result = await db.execute(
        select(Membership)
        .options(selectinload(Membership.user))
        .where(Membership.id == membership.id)
    )

    return result.scalar_one()


async def remove_membership(
    db: AsyncSession,
    membership: Membership,
) -> None:
    if membership.role == MembershipRole.OWNER:
        owner_count_result = await db.execute(
            select(func.count(Membership.id)).where(
                Membership.organization_id == membership.organization_id,
                Membership.role == MembershipRole.OWNER.value,
            )
        )

        owner_count = owner_count_result.scalar_one()

        if owner_count <= 1:
            raise ValueError(
                "The organization must have at least one owner."
            )

        raise ValueError(
            "Owner membership cannot be removed through this endpoint."
        )

    await db.delete(membership)
    await db.commit()
