import uuid

from app.auth.security import hash_password
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User


async def login(
    client,
    email: str,
    password: str = "TestPassword123!",
):
    response = await client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def test_create_organization(
    client,
    test_user,
):
    token = await login(client, test_user.email)

    response = await client.post(
        "/organizations",
        json={
            "name": "Test Organization",
            "slug": "test-organization",
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Test Organization"
    assert data["slug"] == "test-organization"
    assert "id" in data


async def test_create_organization_makes_creator_owner(
    client,
    test_user,
    db_session,
):
    token = await login(client, test_user.email)

    response = await client.post(
        "/organizations",
        json={
            "name": "Owner Test Organization",
            "slug": "owner-test-organization",
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 201

    organization_id = uuid.UUID(response.json()["id"])

    result = await db_session.execute(
        __import__("sqlalchemy").select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == test_user.id,
        )
    )

    membership = result.scalar_one()

    assert membership.role == "owner"


async def test_list_organizations_returns_only_user_organizations(
    client,
    test_user,
    db_session,
):
    token = await login(client, test_user.email)

    first = Organization(
        name="First Organization",
        slug="first-organization",
    )
    second = Organization(
        name="Second Organization",
        slug="second-organization",
    )
    unrelated = Organization(
        name="Unrelated Organization",
        slug="unrelated-organization",
    )

    db_session.add_all([first, second, unrelated])
    await db_session.flush()

    db_session.add_all(
        [
            Membership(
                organization_id=first.id,
                user_id=test_user.id,
                role="owner",
            ),
            Membership(
                organization_id=second.id,
                user_id=test_user.id,
                role="member",
            ),
        ]
    )

    await db_session.commit()

    response = await client.get(
        "/organizations",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert {item["slug"] for item in data} == {
        "first-organization",
        "second-organization",
    }


async def test_get_organization_requires_membership(
    client,
    test_user,
    db_session,
):
    token = await login(client, test_user.email)

    organization = Organization(
        name="Private Organization",
        slug="private-organization",
    )

    db_session.add(organization)
    await db_session.commit()

    response = await client.get(
        f"/organizations/{organization.id}",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "You do not have access to this organization."
    )


async def test_get_organization_as_member(
    client,
    test_user,
    db_session,
):
    token = await login(client, test_user.email)

    organization = Organization(
        name="Member Organization",
        slug="member-organization",
    )

    db_session.add(organization)
    await db_session.flush()

    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=test_user.id,
            role="member",
        )
    )

    await db_session.commit()

    response = await client.get(
        f"/organizations/{organization.id}",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == str(organization.id)
    assert data["name"] == "Member Organization"
    assert data["slug"] == "member-organization"


async def test_duplicate_organization_slug_returns_conflict(
    client,
    test_user,
):
    token = await login(client, test_user.email)

    first_response = await client.post(
        "/organizations",
        json={
            "name": "First Organization",
            "slug": "duplicate-slug",
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert first_response.status_code == 201

    second_response = await client.post(
        "/organizations",
        json={
            "name": "Second Organization",
            "slug": "duplicate-slug",
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert second_response.status_code == 409
    assert second_response.json()["detail"] == (
        "An organization with this slug already exists."
    )


async def test_update_organization_owner(
    client,
    test_user,
):
    token = await login(client, test_user.email)

    create_response = await client.post(
        "/organizations",
        json={
            "name": "Original Organization",
            "slug": "original-organization",
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert create_response.status_code == 201

    organization_id = create_response.json()["id"]

    response = await client.patch(
        f"/organizations/{organization_id}",
        json={
            "name": "Updated Organization",
            "slug": "updated-organization",
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Updated Organization"
    assert data["slug"] == "updated-organization"


async def test_member_cannot_update_organization(
    client,
    test_user,
    db_session,
):
    organization = Organization(
        name="Member Update Test",
        slug="member-update-test",
    )

    db_session.add(organization)
    await db_session.flush()

    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=test_user.id,
            role="member",
        )
    )

    await db_session.commit()

    token = await login(client, test_user.email)

    response = await client.patch(
        f"/organizations/{organization.id}",
        json={
            "name": "Should Not Update",
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 403


async def test_admin_can_update_organization(
    client,
    test_user,
    db_session,
):
    organization = Organization(
        name="Admin Update Test",
        slug="admin-update-test",
    )

    db_session.add(organization)
    await db_session.flush()

    admin = User(
        email="organization-admin@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Organization Admin",
        is_active=True,
    )

    db_session.add(admin)
    await db_session.flush()

    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=admin.id,
            role="admin",
        )
    )

    await db_session.commit()

    token = await login(client, admin.email)

    response = await client.patch(
        f"/organizations/{organization.id}",
        json={
            "name": "Updated By Admin",
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated By Admin"


async def test_owner_can_add_member(
    client,
    test_user,
    db_session,
):
    owner_token = await login(client, test_user.email)

    create_response = await client.post(
        "/organizations",
        json={
            "name": "Add Member Test",
            "slug": "add-member-test",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert create_response.status_code == 201
    organization_id = create_response.json()["id"]

    member = User(
        email="new-member@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="New Member",
        is_active=True,
    )

    db_session.add(member)
    await db_session.flush()

    response = await client.post(
        f"/organizations/{organization_id}/members",
        json={
            "email": member.email,
            "role": "member",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["email"] == member.email
    assert data["role"] == "member"


async def test_admin_can_add_member(
    client,
    test_user,
    db_session,
):
    owner_token = await login(client, test_user.email)

    create_response = await client.post(
        "/organizations",
        json={
            "name": "Admin Add Member Test",
            "slug": "admin-add-member-test",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert create_response.status_code == 201
    organization_id = create_response.json()["id"]

    admin = User(
        email="admin@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Admin User",
        is_active=True,
    )

    member = User(
        email="admin-added-member@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Admin Added Member",
        is_active=True,
    )

    db_session.add_all([admin, member])
    await db_session.flush()

    db_session.add(
        Membership(
            organization_id=uuid.UUID(organization_id),
            user_id=admin.id,
            role="admin",
        )
    )

    await db_session.commit()

    admin_token = await login(client, admin.email)

    response = await client.post(
        f"/organizations/{organization_id}/members",
        json={
            "email": member.email,
            "role": "member",
        },
        headers={
            "Authorization": f"Bearer {admin_token}",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "member"


async def test_member_cannot_add_member(
    client,
    test_user,
    db_session,
):
    organization = Organization(
        name="Member Add Protection Test",
        slug="member-add-protection-test",
    )

    db_session.add(organization)
    await db_session.flush()

    member = User(
        email="existing-member@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Existing Member",
        is_active=True,
    )

    target = User(
        email="target-member@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Target Member",
        is_active=True,
    )

    db_session.add_all([member, target])
    await db_session.flush()

    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=member.id,
            role="member",
        )
    )

    await db_session.commit()

    member_token = await login(client, member.email)

    response = await client.post(
        f"/organizations/{organization.id}/members",
        json={
            "email": target.email,
            "role": "member",
        },
        headers={
            "Authorization": f"Bearer {member_token}",
        },
    )

    assert response.status_code == 403


async def test_add_member_unknown_email_returns_not_found(
    client,
    test_user,
):
    owner_token = await login(client, test_user.email)

    create_response = await client.post(
        "/organizations",
        json={
            "name": "Unknown Member Test",
            "slug": "unknown-member-test",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert create_response.status_code == 201
    organization_id = create_response.json()["id"]

    response = await client.post(
        f"/organizations/{organization_id}/members",
        json={
            "email": "does-not-exist@example.com",
            "role": "member",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "User with this email does not exist."
    )


async def test_add_duplicate_member_returns_conflict(
    client,
    test_user,
    db_session,
):
    owner_token = await login(client, test_user.email)

    create_response = await client.post(
        "/organizations",
        json={
            "name": "Duplicate Member Test",
            "slug": "duplicate-member-test",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert create_response.status_code == 201
    organization_id = create_response.json()["id"]

    member = User(
        email="duplicate-member@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Duplicate Member",
        is_active=True,
    )

    db_session.add(member)
    await db_session.flush()

    first_response = await client.post(
        f"/organizations/{organization_id}/members",
        json={
            "email": member.email,
            "role": "member",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert first_response.status_code == 201

    second_response = await client.post(
        f"/organizations/{organization_id}/members",
        json={
            "email": member.email,
            "role": "member",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert second_response.status_code == 409
    assert second_response.json()["detail"] == (
        "User is already a member of this organization."
    )


async def test_owner_cannot_be_assigned_through_member_endpoint(
    client,
    test_user,
    db_session,
):
    owner_token = await login(client, test_user.email)

    create_response = await client.post(
        "/organizations",
        json={
            "name": "Owner Assignment Test",
            "slug": "owner-assignment-test",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert create_response.status_code == 201
    organization_id = create_response.json()["id"]

    member = User(
        email="owner-assignment-target@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Owner Assignment Target",
        is_active=True,
    )

    db_session.add(member)
    await db_session.flush()

    response = await client.post(
        f"/organizations/{organization_id}/members",
        json={
            "email": member.email,
            "role": "owner",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Owner role cannot be assigned through this endpoint."
    )


async def test_owner_can_change_member_role(
    client,
    test_user,
    db_session,
):
    owner_token = await login(client, test_user.email)

    create_response = await client.post(
        "/organizations",
        json={
            "name": "Owner Role Change Test",
            "slug": "owner-role-change-test",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert create_response.status_code == 201
    organization_id = create_response.json()["id"]

    member = User(
        email="role-change-member@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Role Change Member",
        is_active=True,
    )
    db_session.add(member)
    await db_session.flush()

    add_response = await client.post(
        f"/organizations/{organization_id}/members",
        json={
            "email": member.email,
            "role": "member",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert add_response.status_code == 201
    membership_id = add_response.json()["membership_id"]

    response = await client.patch(
        f"/organizations/{organization_id}/members/{membership_id}",
        json={
            "role": "admin",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_admin_can_change_member_role(
    client,
    test_user,
    db_session,
):
    owner_token = await login(client, test_user.email)

    create_response = await client.post(
        "/organizations",
        json={
            "name": "Admin Role Change Test",
            "slug": "admin-role-change-test",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert create_response.status_code == 201
    organization_id = create_response.json()["id"]

    admin = User(
        email="role-change-admin@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Role Change Admin",
        is_active=True,
    )

    member = User(
        email="role-change-target@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Role Change Target",
        is_active=True,
    )

    db_session.add_all([admin, member])
    await db_session.flush()

    db_session.add(
        Membership(
            organization_id=uuid.UUID(organization_id),
            user_id=admin.id,
            role="admin",
        )
    )
    await db_session.commit()

    admin_token = await login(client, admin.email)

    add_response = await client.post(
        f"/organizations/{organization_id}/members",
        json={
            "email": member.email,
            "role": "member",
        },
        headers={
            "Authorization": f"Bearer {admin_token}",
        },
    )

    assert add_response.status_code == 201
    membership_id = add_response.json()["membership_id"]

    response = await client.patch(
        f"/organizations/{organization_id}/members/{membership_id}",
        json={
            "role": "admin",
        },
        headers={
            "Authorization": f"Bearer {admin_token}",
        },
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_admin_cannot_modify_another_admin(
    client,
    test_user,
    db_session,
):
    owner_token = await login(client, test_user.email)

    create_response = await client.post(
        "/organizations",
        json={
            "name": "Admin Isolation Test",
            "slug": "admin-isolation-test",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert create_response.status_code == 201
    organization_id = create_response.json()["id"]

    admin = User(
        email="first-admin@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="First Admin",
        is_active=True,
    )

    target_admin = User(
        email="second-admin@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Second Admin",
        is_active=True,
    )

    db_session.add_all([admin, target_admin])
    await db_session.flush()

    db_session.add_all(
        [
            Membership(
                organization_id=uuid.UUID(organization_id),
                user_id=admin.id,
                role="admin",
            ),
            Membership(
                organization_id=uuid.UUID(organization_id),
                user_id=target_admin.id,
                role="admin",
            ),
        ]
    )
    await db_session.commit()

    admin_token = await login(client, admin.email)

    target_membership = await db_session.execute(
        __import__("sqlalchemy").select(Membership).where(
            Membership.organization_id == uuid.UUID(organization_id),
            Membership.user_id == target_admin.id,
        )
    )
    target_membership = target_membership.scalar_one()

    response = await client.patch(
        f"/organizations/{organization_id}/members/{target_membership.id}",
        json={
            "role": "member",
        },
        headers={
            "Authorization": f"Bearer {admin_token}",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Admins can only manage members."
    )


async def test_admin_cannot_modify_owner(
    client,
    test_user,
    db_session,
):
    owner_token = await login(client, test_user.email)

    create_response = await client.post(
        "/organizations",
        json={
            "name": "Owner Protection Test",
            "slug": "owner-protection-test",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert create_response.status_code == 201
    organization_id = create_response.json()["id"]

    admin = User(
        email="owner-protection-admin@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Owner Protection Admin",
        is_active=True,
    )
    db_session.add(admin)
    await db_session.flush()

    admin_membership = Membership(
        organization_id=uuid.UUID(organization_id),
        user_id=admin.id,
        role="admin",
    )
    db_session.add(admin_membership)
    await db_session.commit()

    admin_token = await login(client, admin.email)

    owner_membership = await db_session.execute(
        __import__("sqlalchemy").select(Membership).where(
            Membership.organization_id == uuid.UUID(organization_id),
            Membership.user_id == test_user.id,
        )
    )
    owner_membership = owner_membership.scalar_one()

    response = await client.patch(
        f"/organizations/{organization_id}/members/{owner_membership.id}",
        json={
            "role": "member",
        },
        headers={
            "Authorization": f"Bearer {admin_token}",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Admins can only manage members."
    )


async def test_member_cannot_change_membership_role(
    client,
    test_user,
    db_session,
):
    owner_token = await login(client, test_user.email)

    create_response = await client.post(
        "/organizations",
        json={
            "name": "Member Role Protection Test",
            "slug": "member-role-protection-test",
        },
        headers={
            "Authorization": f"Bearer {owner_token}",
        },
    )

    assert create_response.status_code == 201
    organization_id = create_response.json()["id"]

    member = User(
        email="role-protection-member@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Role Protection Member",
        is_active=True,
    )
    target = User(
        email="role-protection-target@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Role Protection Target",
        is_active=True,
    )

    db_session.add_all([member, target])
    await db_session.flush()

    member_membership = Membership(
        organization_id=uuid.UUID(organization_id),
        user_id=member.id,
        role="member",
    )
    target_membership = Membership(
        organization_id=uuid.UUID(organization_id),
        user_id=target.id,
        role="member",
    )

    db_session.add_all([member_membership, target_membership])
    await db_session.commit()

    member_token = await login(client, member.email)

    response = await client.patch(
        f"/organizations/{organization_id}/members/{target_membership.id}",
        json={
            "role": "admin",
        },
        headers={
            "Authorization": f"Bearer {member_token}",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "You do not have permission to perform this action."
    )
