import uuid

import pytest
from fastapi import HTTPException

from app.auth.authorization import (
    MembershipRole,
    can_manage_memberships,
    require_membership_management,
    validate_membership_role_assignment,
)
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User


def test_owner_can_manage_any_role():
    assert can_manage_memberships(
        MembershipRole.OWNER,
        MembershipRole.OWNER,
    )
    assert can_manage_memberships(
        MembershipRole.OWNER,
        MembershipRole.ADMIN,
    )
    assert can_manage_memberships(
        MembershipRole.OWNER,
        MembershipRole.MEMBER,
    )


def test_admin_can_manage_member_only():
    assert can_manage_memberships(
        MembershipRole.ADMIN,
        MembershipRole.MEMBER,
    )

    assert not can_manage_memberships(
        MembershipRole.ADMIN,
        MembershipRole.ADMIN,
    )

    assert not can_manage_memberships(
        MembershipRole.ADMIN,
        MembershipRole.OWNER,
    )


def test_member_cannot_manage_memberships():
    assert not can_manage_memberships(
        MembershipRole.MEMBER,
        MembershipRole.MEMBER,
    )
    assert not can_manage_memberships(
        MembershipRole.MEMBER,
        MembershipRole.ADMIN,
    )
    assert not can_manage_memberships(
        MembershipRole.MEMBER,
        MembershipRole.OWNER,
    )


def test_owner_role_cannot_be_assigned_generically():
    with pytest.raises(HTTPException) as exc_info:
        validate_membership_role_assignment(MembershipRole.OWNER)

    assert exc_info.value.status_code == 400


def test_admin_role_can_be_assigned():
    validate_membership_role_assignment(MembershipRole.ADMIN)


def test_member_role_can_be_assigned():
    validate_membership_role_assignment(MembershipRole.MEMBER)


async def test_member_can_access_organization(db_session):
    from app.auth.authorization import get_organization_access

    user = User(
        email="authz-user@example.com",
        password_hash="test-hash",
        full_name="Authz User",
        is_active=True,
    )

    organization = Organization(
        name="Authz Organization",
        slug=f"authz-{uuid.uuid4().hex}",
    )

    db_session.add_all([user, organization])
    await db_session.flush()

    membership = Membership(
        user_id=user.id,
        organization_id=organization.id,
        role="member",
    )

    db_session.add(membership)
    await db_session.flush()

    access = await get_organization_access(
        organization_id=organization.id,
        current_user=user,
        db=db_session,
    )

    assert access.user.id == user.id
    assert access.membership.organization_id == organization.id
    assert access.membership.role == "member"


async def test_non_member_cannot_access_organization(db_session):
    from app.auth.authorization import get_organization_access

    user = User(
        email="nonmember@example.com",
        password_hash="test-hash",
        full_name="Non Member",
        is_active=True,
    )

    organization = Organization(
        name="Private Organization",
        slug=f"private-{uuid.uuid4().hex}",
    )

    db_session.add_all([user, organization])
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await get_organization_access(
            organization_id=organization.id,
            current_user=user,
            db=db_session,
        )

    assert exc_info.value.status_code == 403
