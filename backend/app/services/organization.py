from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.membership import Membership
from app.models.organization import Organization


async def create_organization(
    db: AsyncSession,
    name: str,
    slug: str,
    owner_user_id: uuid.UUID,
) -> Organization:
    organization = Organization(
        name=name,
        slug=slug,
    )
    db.add(organization)

    await db.flush()

    membership = Membership(
        organization_id=organization.id,
        user_id=owner_user_id,
        role="owner",
    )
    db.add(membership)

    await db.commit()
    await db.refresh(organization)

    return organization


async def get_organization(
    db: AsyncSession,
    organization_id: uuid.UUID,
) -> Organization | None:
    result = await db.execute(
        select(Organization).where(
            Organization.id == organization_id,
        )
    )
    return result.scalar_one_or_none()


async def update_organization(
    db: AsyncSession,
    organization: Organization,
    name: str | None = None,
    slug: str | None = None,
) -> Organization:
    if name is not None:
        organization.name = name

    if slug is not None:
        organization.slug = slug

    await db.commit()
    await db.refresh(organization)

    return organization


async def delete_organization(
    db: AsyncSession,
    organization: Organization,
) -> None:
    await db.delete(organization)
    await db.commit()

async def list_user_organizations(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[Organization]:
    result = await db.execute(
        select(Organization)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user_id)
        .order_by(Organization.name)
    )
    return list(result.scalars().all())