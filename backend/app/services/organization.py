from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.membership import Membership
from app.models.organization import Organization
from app.storage.base import StorageService

logger = logging.getLogger(__name__)


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
    storage: StorageService,
) -> None:
    """Delete an organization and clean up its stored document files."""
    result = await db.execute(
        select(DocumentVersion.storage_object_key)
        .join(
            Document,
            Document.id == DocumentVersion.document_id,
        )
        .where(Document.organization_id == organization.id)
    )
    storage_keys = list(result.scalars().all())

    try:
        await db.delete(organization)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    # Database deletion is committed before touching external storage.
    for storage_key in storage_keys:
        try:
            if storage.exists(storage_key):
                storage.delete(storage_key)
        except Exception:
            logger.exception(
                "Failed to delete storage object after organization deletion: %s",
                storage_key,
            )


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