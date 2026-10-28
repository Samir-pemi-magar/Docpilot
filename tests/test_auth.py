async def test_login_success(client, test_user):
    response = await client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["access_token"]


async def test_login_wrong_password(client, test_user):
    response = await client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password."


async def test_login_unknown_email(client):
    response = await client.post(
        "/auth/login",
        json={
            "email": "unknown@example.com",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password."


async def test_get_me_with_valid_token(client, test_user):
    login_response = await client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "TestPassword123!",
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    response = await client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == str(test_user.id)
    assert data["email"] == test_user.email
    assert data["full_name"] == test_user.full_name
    assert data["is_active"] is True


async def test_get_me_without_token(client):
    response = await client.get("/auth/me")

    assert response.status_code == 401


async def test_register_creates_account_and_allows_login(client):
    import uuid

    email = f"register-{uuid.uuid4().hex}@example.com"
    payload = {
        "full_name": "Registration Test",
        "email": email,
        "password": "SecureTestPass123!",
    }

    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == email
    assert data["full_name"] == payload["full_name"]
    assert data["is_active"] is True
    assert "password_hash" not in data

    login_response = await client.post(
        "/auth/login",
        json={"email": email, "password": payload["password"]},
    )
    assert login_response.status_code == 200
    assert login_response.json()["access_token"]


async def test_register_rejects_duplicate_email(client):
    import uuid

    payload = {
        "full_name": "Registration Test",
        "email": f"duplicate-{uuid.uuid4().hex}@example.com",
        "password": "SecureTestPass123!",
    }

    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 409


async def test_register_rejects_short_password(client):
    response = await client.post(
        "/auth/register",
        json={
            "full_name": "Short Password",
            "email": "short-password@example.com",
            "password": "123",
        },
    )
    assert response.status_code == 422


async def test_delete_account_requires_authentication(client):
    response = await client.request("DELETE",
        "/auth/me",
        json={"password": "TestPassword123!"},
    )

    assert response.status_code == 401


async def test_delete_account_rejects_wrong_password(client, test_user):
    login_response = await client.post(
        "/auth/login",
        json={
            "email": test_user.email,
            "password": "TestPassword123!",
        },
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    response = await client.request("DELETE",
        "/auth/me",
        json={"password": "WrongPassword123!"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect password."


async def test_delete_account_rejects_organization_owner(
    client, test_user, db_session
):
    import uuid

    from sqlalchemy import select

    from app.models.membership import Membership
    from app.models.organization import Organization
    from app.models.user import User

    organization = Organization(
        name="Owned Organization",
        slug=f"owned-{uuid.uuid4().hex}",
    )
    db_session.add(organization)
    await db_session.flush()

    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=test_user.id,
            role="owner",
        )
    )
    await db_session.flush()

    login_response = await client.post(
        "/auth/login",
        json={
            "email": test_user.email,
            "password": "TestPassword123!",
        },
    )
    token = login_response.json()["access_token"]

    response = await client.request("DELETE",
        "/auth/me",
        json={"password": "TestPassword123!"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert "organizations you own" in response.json()["detail"]

    user_result = await db_session.execute(
        select(User.id).where(User.id == test_user.id)
    )
    assert user_result.scalar_one_or_none() == test_user.id


async def test_delete_account_preserves_shared_documents_and_evaluations(
    client, test_user, db_session
):
    import uuid

    from sqlalchemy import func, select

    from app.models.conversation import Conversation
    from app.models.document import Document
    from app.models.document_version import DocumentVersion
    from app.models.evaluation_dataset import EvaluationDataset
    from app.models.evaluation_run import EvaluationRun
    from app.models.membership import Membership
    from app.models.organization import Organization
    from app.models.user import User

    owner = User(
        email=f"owner-{uuid.uuid4().hex}@example.com",
        password_hash=test_user.password_hash,
        full_name="Organization Owner",
        is_active=True,
    )
    organization = Organization(
        name="Shared Organization",
        slug=f"shared-{uuid.uuid4().hex}",
    )
    db_session.add_all([owner, organization])
    await db_session.flush()

    db_session.add_all(
        [
            Membership(
                organization_id=organization.id,
                user_id=owner.id,
                role="owner",
            ),
            Membership(
                organization_id=organization.id,
                user_id=test_user.id,
                role="member",
            ),
        ]
    )

    document = Document(
        organization_id=organization.id,
        created_by_user_id=test_user.id,
        name="Shared document",
    )
    db_session.add(document)
    await db_session.flush()

    version = DocumentVersion(
        document_id=document.id,
        uploaded_by_user_id=test_user.id,
        version_number=1,
        original_filename="shared.txt",
        content_type="text/plain",
        size_bytes=5,
        storage_object_key=(
            f"organizations/{organization.id}/documents/"
            f"{document.id}/versions/1/original.txt"
        ),
        sha256="a" * 64,
    )
    dataset = EvaluationDataset(
        organization_id=organization.id,
        created_by_user_id=test_user.id,
        name="Shared evaluation dataset",
    )
    db_session.add(dataset)
    await db_session.flush()

    evaluation_run = EvaluationRun(
        dataset_id=dataset.id,
        started_by_user_id=test_user.id,
        status="completed",
        total_cases=1,
        completed_cases=1,
        metrics={"accuracy": 1.0},
    )
    conversation = Conversation(
        organization_id=organization.id,
        created_by_user_id=test_user.id,
        title="Personal conversation",
    )
    db_session.add_all([version, evaluation_run, conversation])
    await db_session.flush()

    document_id = document.id
    version_id = version.id
    dataset_id = dataset.id
    evaluation_run_id = evaluation_run.id
    conversation_id = conversation.id
    organization_id = organization.id
    user_id = test_user.id

    login_response = await client.post(
        "/auth/login",
        json={
            "email": test_user.email,
            "password": "TestPassword123!",
        },
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    response = await client.request("DELETE",
        "/auth/me",
        json={"password": "TestPassword123!"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204
    assert response.content == b""

    # The user is deleted.
    assert await db_session.scalar(
        select(User.id).where(User.id == user_id)
    ) is None

    # The organization and its other owner's membership survive.
    assert await db_session.scalar(
        select(Organization.id).where(
            Organization.id == organization_id
        )
    ) == organization_id

    assert await db_session.scalar(
        select(func.count()).select_from(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == owner.id,
        )
    ) == 1

    # The shared document and version survive without deleted-user attribution.
    assert await db_session.scalar(
        select(Document.id).where(Document.id == document_id)
    ) == document_id

    assert await db_session.scalar(
        select(Document.created_by_user_id).where(
            Document.id == document_id
        )
    ) is None

    assert await db_session.scalar(
        select(DocumentVersion.id).where(
            DocumentVersion.id == version_id
        )
    ) == version_id

    assert await db_session.scalar(
        select(DocumentVersion.uploaded_by_user_id).where(
            DocumentVersion.id == version_id
        )
    ) is None

    # The evaluation dataset survives; its creator attribution is cleared.
    assert await db_session.scalar(
        select(EvaluationDataset.id).where(
            EvaluationDataset.id == dataset_id
        )
    ) == dataset_id

    assert await db_session.scalar(
        select(EvaluationDataset.created_by_user_id).where(
            EvaluationDataset.id == dataset_id
        )
    ) is None

    # Evaluation history survives, without the deleted user's attribution.
    assert await db_session.scalar(
        select(EvaluationRun.id).where(
            EvaluationRun.id == evaluation_run_id
        )
    ) == evaluation_run_id

    assert await db_session.scalar(
        select(EvaluationRun.started_by_user_id).where(
            EvaluationRun.id == evaluation_run_id
        )
    ) is None

    assert await db_session.scalar(
        select(EvaluationRun.status).where(
            EvaluationRun.id == evaluation_run_id
        )
    ) == "completed"

    assert await db_session.scalar(
        select(EvaluationRun.metrics).where(
            EvaluationRun.id == evaluation_run_id
        )
    ) == {"accuracy": 1.0}

    # Conversations are personal and cascade-delete with their creator.
    assert await db_session.scalar(
        select(Conversation.id).where(
            Conversation.id == conversation_id
        )
    ) is None


async def test_refresh_token_returns_new_token_pair(client, test_user):
    login = await client.post(
        "/auth/login",
        json={
            "email": test_user.email,
            "password": "TestPassword123!",
        },
    )
    assert login.status_code == 200
    original = login.json()
    assert original["refresh_token"]

    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": original["refresh_token"]},
    )

    assert response.status_code == 200
    refreshed = response.json()
    assert refreshed["access_token"]
    assert refreshed["refresh_token"]

    # JWTs created within the same second can be identical.
    # Check that the refreshed access token actually works.
    me = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {refreshed['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["id"] == str(test_user.id)


async def test_refresh_rejects_access_token(client, test_user):
    from app.auth.security import create_access_token
    from datetime import timedelta

    access_token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(minutes=5),
    )

    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": access_token},
    )

    assert response.status_code == 401


async def test_refresh_rejects_malformed_token(client):
    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": "not-a-valid-jwt"},
    )

    assert response.status_code == 401


async def test_refresh_rejects_expired_token(client, test_user):
    from datetime import timedelta
    from app.auth.security import create_refresh_token

    expired_token = create_refresh_token(
        subject=str(test_user.id),
        expires_delta=timedelta(seconds=-10),
    )

    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": expired_token},
    )

    assert response.status_code == 401


async def test_refresh_rejects_inactive_user(client, test_user, db_session):
    login = await client.post(
        "/auth/login",
        json={
            "email": test_user.email,
            "password": "TestPassword123!",
        },
    )
    assert login.status_code == 200
    refresh_token = login.json()["refresh_token"]

    test_user.is_active = False
    await db_session.flush()

    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 401
