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
