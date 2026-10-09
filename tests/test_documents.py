import uuid

from sqlalchemy import select

from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.membership import Membership
from app.models.organization import Organization
from app.api.dependencies import get_document_ingestion_task
from app.main import app


PASSWORD = "TestPassword123!"


async def login(client, email):
    response = await client.post(
        "/auth/login",
        json={
            "email": email,
            "password": PASSWORD,
        },
    )

    assert response.status_code == 200

    return response.json()["access_token"]


async def create_user(db_session, email, full_name):
    from app.auth.security import hash_password
    from app.models.user import User

    user = User(
        email=email,
        password_hash=hash_password(PASSWORD),
        full_name=full_name,
        is_active=True,
    )

    db_session.add(user)
    await db_session.flush()

    return user


async def create_organization(
    db_session,
    owner_id,
    name,
    slug,
):
    organization = Organization(
        name=name,
        slug=slug,
    )

    db_session.add(organization)
    await db_session.flush()

    membership = Membership(
        organization_id=organization.id,
        user_id=owner_id,
        role="owner",
    )

    db_session.add(membership)
    await db_session.flush()

    return organization


async def add_membership(
    db_session,
    organization_id,
    user_id,
    role,
):
    membership = Membership(
        organization_id=organization_id,
        user_id=user_id,
        role=role,
    )

    db_session.add(membership)
    await db_session.flush()

    return membership


async def upload_document(
    client,
    token,
    organization_id,
    name="Test Document",
    filename="hello.txt",
    content=b"Hello document!",
):
    return await client.post(
        f"/organizations/{organization_id}/documents",
        data={
            "name": name,
        },
        files={
            "file": (
                filename,
                content,
                "text/plain",
            )
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )


async def test_owner_can_upload_document(
    client,
    db_session,
):
    owner = await create_user(
        db_session,
        "owner@example.com",
        "Owner",
    )

    organization = await create_organization(
        db_session,
        owner.id,
        "Test Organization",
        "test-organization",
    )

    token = await login(client, owner.email)

    response = await upload_document(
        client,
        token,
        organization.id,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["version_number"] == 1
    assert data["ingestion_status"] == "pending"
    assert data["original_filename"] == "hello.txt"
    assert data["content_type"] == "text/plain"
    assert data["size_bytes"] == len(b"Hello document!")
    assert data["sha256"] == (
        "ce551ef53a3fcef80c8df2a78661597d84cdd45a8493c2d146c36d18c3307eb8"
    )


async def test_admin_can_upload_document(
    client,
    db_session,
):
    owner = await create_user(
        db_session,
        "owner@example.com",
        "Owner",
    )

    admin = await create_user(
        db_session,
        "admin@example.com",
        "Admin",
    )

    organization = await create_organization(
        db_session,
        owner.id,
        "Test Organization",
        "test-organization",
    )

    await add_membership(
        db_session,
        organization.id,
        admin.id,
        "admin",
    )

    token = await login(client, admin.email)

    response = await upload_document(
        client,
        token,
        organization.id,
    )

    assert response.status_code == 201


async def test_member_cannot_upload_document(
    client,
    db_session,
):
    owner = await create_user(
        db_session,
        "owner@example.com",
        "Owner",
    )

    member = await create_user(
        db_session,
        "member@example.com",
        "Member",
    )

    organization = await create_organization(
        db_session,
        owner.id,
        "Test Organization",
        "test-organization",
    )

    await add_membership(
        db_session,
        organization.id,
        member.id,
        "member",
    )

    token = await login(client, member.email)

    response = await upload_document(
        client,
        token,
        organization.id,
    )

    assert response.status_code == 403


async def test_uploaded_document_appears_in_list(
    client,
    db_session,
):
    owner = await create_user(
        db_session,
        "owner@example.com",
        "Owner",
    )

    organization = await create_organization(
        db_session,
        owner.id,
        "Test Organization",
        "test-organization",
    )

    token = await login(client, owner.email)

    upload_response = await upload_document(
        client,
        token,
        organization.id,
        name="My Document",
    )

    assert upload_response.status_code == 201

    response = await client.get(
        f"/organizations/{organization.id}/documents",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    documents = response.json()

    assert len(documents) == 1
    assert documents[0]["name"] == "My Document"
    assert documents[0]["organization_id"] == str(organization.id)


async def test_member_can_retrieve_document(
    client,
    db_session,
):
    owner = await create_user(
        db_session,
        "owner@example.com",
        "Owner",
    )

    member = await create_user(
        db_session,
        "member@example.com",
        "Member",
    )

    organization = await create_organization(
        db_session,
        owner.id,
        "Test Organization",
        "test-organization",
    )

    await add_membership(
        db_session,
        organization.id,
        member.id,
        "member",
    )

    owner_token = await login(client, owner.email)

    upload_response = await upload_document(
        client,
        owner_token,
        organization.id,
    )

    document_id = upload_response.json()["id"]

    print("\nDEBUG document_id:", document_id)
    debug_result = await db_session.execute(
        select(Document).where(Document.id == uuid.UUID(document_id))
    )
    debug_document = debug_result.scalar_one_or_none()
    print("DEBUG document in db_session:", debug_document)

    member_token = await login(client, member.email)

    response = await client.get(
        f"/organizations/{organization.id}/documents/{document_id}",
        headers={
            "Authorization": f"Bearer {member_token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == document_id
    assert data["name"] == "Test Document"
    assert len(data["versions"]) == 1
    assert data["versions"][0]["version_number"] == 1


async def test_non_member_cannot_retrieve_document(
    client,
    db_session,
):
    owner = await create_user(
        db_session,
        "owner@example.com",
        "Owner",
    )

    outsider = await create_user(
        db_session,
        "outsider@example.com",
        "Outsider",
    )

    organization = await create_organization(
        db_session,
        owner.id,
        "Test Organization",
        "test-organization",
    )

    owner_token = await login(client, owner.email)

    upload_response = await upload_document(
        client,
        owner_token,
        organization.id,
    )

    document_id = upload_response.json()["id"]

    outsider_token = await login(client, outsider.email)

    response = await client.get(
        f"/organizations/{organization.id}/documents/{document_id}",
        headers={
            "Authorization": f"Bearer {outsider_token}",
        },
    )

    assert response.status_code == 403


async def test_new_version_increments_version_number(
    client,
    db_session,
):
    owner = await create_user(
        db_session,
        "owner@example.com",
        "Owner",
    )

    organization = await create_organization(
        db_session,
        owner.id,
        "Test Organization",
        "test-organization",
    )

    token = await login(client, owner.email)

    first_response = await upload_document(
        client,
        token,
        organization.id,
        content=b"Version one",
    )

    assert first_response.status_code == 201

    document_id = first_response.json()["id"]

    second_response = await client.post(
        f"/organizations/{organization.id}/documents/{document_id}/versions",
        files={
            "file": (
                "updated.txt",
                b"Version two",
                "text/plain",
            )
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert second_response.status_code == 201

    data = second_response.json()

    assert data["version_number"] == 2
    assert data["ingestion_status"] == "pending"
    assert data["original_filename"] == "updated.txt"
    assert data["size_bytes"] == len(b"Version two")


async def test_download_returns_stored_bytes(
    client,
    db_session,
):
    owner = await create_user(
        db_session,
        "owner@example.com",
        "Owner",
    )

    organization = await create_organization(
        db_session,
        owner.id,
        "Test Organization",
        "test-organization",
    )

    token = await login(client, owner.email)

    content = b"This is the actual stored document."

    upload_response = await upload_document(
        client,
        token,
        organization.id,
        content=content,
    )

    assert upload_response.status_code == 201

    document_id = upload_response.json()["id"]

    response = await client.get(
        f"/organizations/{organization.id}/documents/"
        f"{document_id}/versions/1/download",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "text/plain"
    assert "hello.txt" in response.headers["content-disposition"]


async def test_delete_removes_document_and_storage(
    client,
    db_session,
    test_storage,
):
    owner = await create_user(
        db_session,
        "owner@example.com",
        "Owner",
    )

    organization = await create_organization(
        db_session,
        owner.id,
        "Test Organization",
        "test-organization",
    )

    token = await login(client, owner.email)

    upload_response = await upload_document(
        client,
        token,
        organization.id,
    )

    assert upload_response.status_code == 201

    document_id = uuid.UUID(upload_response.json()["id"])

    result = await db_session.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document_id
        )
    )

    version = result.scalar_one()

    storage_key = version.storage_object_key

    assert test_storage.exists(storage_key)

    delete_response = await client.delete(
        f"/organizations/{organization.id}/documents/{document_id}",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert delete_response.status_code == 204

    assert not test_storage.exists(storage_key)

    document_result = await db_session.execute(
        select(Document).where(
            Document.id == document_id
        )
    )

    assert document_result.scalar_one_or_none() is None

    version_result = await db_session.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document_id
        )
    )

    assert version_result.scalars().all() == []


async def test_cross_organization_version_access_is_denied(
    client,
    db_session,
):
    owner_a = await create_user(
        db_session,
        "owner-a@example.com",
        "Owner A",
    )

    owner_b = await create_user(
        db_session,
        "owner-b@example.com",
        "Owner B",
    )

    organization_a = await create_organization(
        db_session,
        owner_a.id,
        "Organization A",
        "organization-a",
    )

    organization_b = await create_organization(
        db_session,
        owner_b.id,
        "Organization B",
        "organization-b",
    )

    token_a = await login(client, owner_a.email)

    upload_response = await upload_document(
        client,
        token_a,
        organization_a.id,
    )

    assert upload_response.status_code == 201

    document_id = upload_response.json()["id"]

    token_b = await login(client, owner_b.email)

    response = await client.get(
        f"/organizations/{organization_b.id}/documents/"
        f"{document_id}/versions/1",
        headers={
            "Authorization": f"Bearer {token_b}",
        },
    )

    assert response.status_code == 404


async def test_upload_and_new_version_schedule_ingestion(
    client,
    db_session,
):
    owner = await create_user(
        db_session,
        "ingestion-owner@example.com",
        "Ingestion Owner",
    )

    organization = await create_organization(
        db_session,
        owner.id,
        "Ingestion Test Organization",
        "ingestion-test-organization",
    )

    token = await login(client, owner.email)
    scheduled_version_ids = []

    async def record_ingestion_task(version_id):
        scheduled_version_ids.append(version_id)

    previous_override = app.dependency_overrides[
        get_document_ingestion_task
    ]
    app.dependency_overrides[get_document_ingestion_task] = (
        lambda: record_ingestion_task
    )

    try:
        first_response = await upload_document(
            client,
            token,
            organization.id,
            content=b"First version",
        )

        assert first_response.status_code == 201
        first_data = first_response.json()
        assert first_data["ingestion_status"] == "pending"

        document_id = first_data["id"]
        first_version_id = first_data["version_id"]

        second_response = await client.post(
            f"/organizations/{organization.id}/documents/"
            f"{document_id}/versions",
            files={
                "file": (
                    "second.txt",
                    b"Second version",
                    "text/plain",
                )
            },
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert second_response.status_code == 201
        second_data = second_response.json()
        assert second_data["version_number"] == 2
        assert second_data["ingestion_status"] == "pending"

        assert scheduled_version_ids == [
            uuid.UUID(first_version_id),
            uuid.UUID(second_data["id"]),
        ]
    finally:
        app.dependency_overrides[
            get_document_ingestion_task
        ] = previous_override
