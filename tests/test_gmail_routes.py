import uuid
from datetime import timedelta

import pytest

from app.api.routes import gmail as gmail_routes


@pytest.mark.asyncio
async def test_gmail_oauth_start_requires_authentication(
    client,
    test_organization,
):
    response = await client.post(
        f"/organizations/{test_organization.id}/gmail/oauth/start"
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_gmail_oauth_start_requires_organization_membership(
    client,
    test_user,
):
    from app.auth.security import create_access_token

    token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(minutes=30),
    )

    response = await client.post(
        f"/organizations/{uuid.uuid4()}/gmail/oauth/start",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_gmail_oauth_start_returns_503_when_not_configured(
    client,
    test_user,
    test_organization,
    db_session,
    monkeypatch,
):
    from app.auth.security import create_access_token
    from app.models.membership import Membership

    db_session.add(
        Membership(
            user_id=test_user.id,
            organization_id=test_organization.id,
            role="owner",
        )
    )
    await db_session.flush()

    class SettingsWithoutGoogleOAuth:
        gmail_client_id = None
        gmail_redirect_uri = None

    monkeypatch.setattr(
        gmail_routes,
        "get_settings",
        lambda: SettingsWithoutGoogleOAuth(),
    )

    token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(minutes=30),
    )

    response = await client.post(
        f"/organizations/{test_organization.id}/gmail/oauth/start",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Gmail OAuth is not configured."


@pytest.mark.asyncio
async def test_gmail_oauth_start_returns_readonly_authorization_url(
    client,
    test_user,
    test_organization,
    db_session,
    monkeypatch,
):
    from datetime import timedelta
    from urllib.parse import parse_qs, urlparse

    from app.auth.security import create_access_token
    from app.models.gmail_oauth_state import GmailOAuthState
    from app.models.membership import Membership
    from app.services.gmail_oauth import GMAIL_READONLY_SCOPE
    from sqlalchemy import select

    class ConfiguredGoogleOAuth:
        gmail_client_id = "test-google-client-id"
        gmail_redirect_uri = (
            "http://127.0.0.1:8000/gmail/oauth/callback"
        )

    # The route and URL builder each read settings independently.
    monkeypatch.setattr(
        gmail_routes,
        "get_settings",
        lambda: ConfiguredGoogleOAuth(),
    )

    from app.services import gmail_oauth

    monkeypatch.setattr(
        gmail_oauth,
        "get_settings",
        lambda: ConfiguredGoogleOAuth(),
    )

    db_session.add(
        Membership(
            user_id=test_user.id,
            organization_id=test_organization.id,
            role="owner",
        )
    )
    await db_session.flush()

    token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(minutes=30),
    )

    response = await client.post(
        f"/organizations/{test_organization.id}/gmail/oauth/start",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    authorization_url = response.json()["authorization_url"]
    parsed_url = urlparse(authorization_url)
    parameters = parse_qs(parsed_url.query)

    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "accounts.google.com"
    assert parameters["client_id"] == ["test-google-client-id"]
    assert parameters["redirect_uri"] == [
        "http://127.0.0.1:8000/gmail/oauth/callback"
    ]
    assert parameters["response_type"] == ["code"]
    assert parameters["scope"] == [GMAIL_READONLY_SCOPE]
    assert parameters["access_type"] == ["offline"]
    assert parameters["state"]

    state = parameters["state"][0]
    state_record = await db_session.scalar(
        select(GmailOAuthState).where(
            GmailOAuthState.user_id == test_user.id,
            GmailOAuthState.organization_id == test_organization.id,
        )
    )

    assert state_record is not None
    assert state_record.state_hash != state
    assert len(state_record.state_hash) == 64
    assert state_record.consumed_at is None


@pytest.mark.asyncio
async def test_gmail_callback_creates_connection(
    client,
    test_user,
    test_organization,
    db_session,
    monkeypatch,
):
    from app.models.gmail_connection import GmailConnection
    from app.services import gmail_google_client
    from app.services.gmail_oauth_state import create_gmail_oauth_state
    from sqlalchemy import select

    async def fake_exchange(code):
        assert code == "test-auth-code"
        return gmail_google_client.GmailOAuthGrant(
            email="mailbox@example.com",
            refresh_token="test-refresh-token",
            scopes="https://www.googleapis.com/auth/gmail.readonly",
        )

    monkeypatch.setattr(
        gmail_google_client,
        "exchange_code_for_gmail_grant",
        fake_exchange,
    )

    from app.services import gmail_tokens

    monkeypatch.setattr(
        gmail_tokens,
        "encrypt_gmail_token",
        lambda token: f"encrypted:{token}",
    )

    state = await create_gmail_oauth_state(
        db_session,
        user_id=test_user.id,
        organization_id=test_organization.id,
    )

    response = await client.get(
        "/gmail/oauth/callback",
        params={"code": "test-auth-code", "state": state},
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "http://127.0.0.1:8443/?gmail=connected&organization_id="
    )
    assert str(test_organization.id) in response.headers["location"]

    result = await db_session.execute(
        select(GmailConnection).where(
            GmailConnection.user_id == test_user.id,
            GmailConnection.organization_id == test_organization.id,
        )
    )
    connection = result.scalar_one()
    assert connection.google_email == "mailbox@example.com"
    assert connection.encrypted_refresh_token == "encrypted:test-refresh-token"
    assert connection.status == "active"


@pytest.mark.asyncio
async def test_gmail_callback_rejects_invalid_or_reused_state(client):
    response = await client.get(
        "/gmail/oauth/callback",
        params={"code": "test-auth-code", "state": "not-a-valid-state"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Invalid or expired Gmail authorization state."
    )


@pytest.mark.asyncio
async def test_gmail_callback_handles_google_authorization_denial(
    client,
    test_user,
    test_organization,
    db_session,
):
    from app.services.gmail_oauth_state import create_gmail_oauth_state

    state = await create_gmail_oauth_state(
        db_session,
        user_id=test_user.id,
        organization_id=test_organization.id,
    )

    response = await client.get(
        "/gmail/oauth/callback",
        params={"error": "access_denied", "state": state},
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "http://127.0.0.1:8443/?gmail=cancelled&organization_id="
    )
    assert str(test_organization.id) in response.headers["location"]


@pytest.mark.asyncio
async def test_gmail_callback_reconnect_preserves_refresh_token_if_google_omits_one(
    client,
    test_user,
    test_organization,
    db_session,
    monkeypatch,
):
    from app.models.gmail_connection import GmailConnection
    from app.services import gmail_google_client, gmail_tokens
    from app.services.gmail_oauth_state import create_gmail_oauth_state

    existing = GmailConnection(
        user_id=test_user.id,
        organization_id=test_organization.id,
        google_email="old-mailbox@example.com",
        encrypted_refresh_token="existing-encrypted-token",
        scopes="https://www.googleapis.com/auth/gmail.readonly",
        status="revoked",
    )
    db_session.add(existing)
    await db_session.flush()

    async def fake_exchange(code):
        return gmail_google_client.GmailOAuthGrant(
            email="new-mailbox@example.com",
            refresh_token=None,
            scopes="https://www.googleapis.com/auth/gmail.readonly",
        )

    monkeypatch.setattr(
        gmail_google_client,
        "exchange_code_for_gmail_grant",
        fake_exchange,
    )
    monkeypatch.setattr(
        gmail_tokens,
        "encrypt_gmail_token",
        lambda token: f"encrypted:{token}",
    )

    state = await create_gmail_oauth_state(
        db_session,
        user_id=test_user.id,
        organization_id=test_organization.id,
    )

    response = await client.get(
        "/gmail/oauth/callback",
        params={"code": "reconnect-code", "state": state},
    )

    assert response.status_code == 303
    assert "gmail=connected" in response.headers["location"]
    await db_session.refresh(existing)
    assert existing.google_email == "old-mailbox@example.com"
    assert existing.encrypted_refresh_token == "existing-encrypted-token"
    assert existing.status == "active"


@pytest.mark.asyncio
async def test_gmail_callback_handles_google_verification_failure(
    client,
    test_user,
    test_organization,
    db_session,
    monkeypatch,
):
    from sqlalchemy import select

    from app.models.gmail_connection import GmailConnection
    from app.services import gmail_google_client
    from app.services.gmail_oauth_state import create_gmail_oauth_state

    async def failed_exchange(code):
        raise gmail_google_client.GmailGoogleAPIError(
            "Google verification failed."
        )

    monkeypatch.setattr(
        gmail_google_client,
        "exchange_code_for_gmail_grant",
        failed_exchange,
    )

    state = await create_gmail_oauth_state(
        db_session,
        user_id=test_user.id,
        organization_id=test_organization.id,
    )

    response = await client.get(
        "/gmail/oauth/callback",
        params={"code": "invalid-code", "state": state},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Google Gmail authorization could not be verified."
    )

    result = await db_session.execute(
        select(GmailConnection).where(
            GmailConnection.user_id == test_user.id,
            GmailConnection.organization_id == test_organization.id,
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_gmail_callback_rejects_missing_authorization_code(
    client,
    test_user,
    test_organization,
    db_session,
):
    from app.services.gmail_oauth_state import create_gmail_oauth_state

    state = await create_gmail_oauth_state(
        db_session,
        user_id=test_user.id,
        organization_id=test_organization.id,
    )

    response = await client.get(
        "/gmail/oauth/callback",
        params={"state": state},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Google did not return an authorization code."
    )


@pytest.mark.asyncio
async def test_gmail_callback_rejects_first_connection_without_refresh_token(
    client,
    test_user,
    test_organization,
    db_session,
    monkeypatch,
):
    from sqlalchemy import select

    from app.models.gmail_connection import GmailConnection
    from app.services import gmail_google_client
    from app.services.gmail_oauth_state import create_gmail_oauth_state

    async def exchange_without_refresh_token(code):
        return gmail_google_client.GmailOAuthGrant(
            email="mailbox@example.com",
            refresh_token=None,
            scopes="https://www.googleapis.com/auth/gmail.readonly",
        )

    monkeypatch.setattr(
        gmail_google_client,
        "exchange_code_for_gmail_grant",
        exchange_without_refresh_token,
    )

    state = await create_gmail_oauth_state(
        db_session,
        user_id=test_user.id,
        organization_id=test_organization.id,
    )

    response = await client.get(
        "/gmail/oauth/callback",
        params={"code": "test-auth-code", "state": state},
    )

    assert response.status_code == 400
    assert "did not provide a refresh token" in response.json()["detail"]

    result = await db_session.execute(
        select(GmailConnection).where(
            GmailConnection.user_id == test_user.id,
            GmailConnection.organization_id == test_organization.id,
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_gmail_status_requires_authentication(client, test_organization):
    response = await client.get(
        f"/organizations/{test_organization.id}/gmail/status"
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_gmail_status_requires_organization_membership(
    client, test_user, test_organization
):
    from app.auth.security import create_access_token

    token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(minutes=30),
    )
    response = await client.get(
        f"/organizations/{test_organization.id}/gmail/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_gmail_status_returns_not_connected(
    client, test_user, test_organization, db_session
):
    from app.auth.security import create_access_token
    from app.models.membership import Membership

    db_session.add(
        Membership(
            user_id=test_user.id,
            organization_id=test_organization.id,
            role="owner",
        )
    )
    await db_session.flush()

    token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(minutes=30),
    )
    response = await client.get(
        f"/organizations/{test_organization.id}/gmail/status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "connected": False,
        "status": "not_connected",
    }


@pytest.mark.asyncio
async def test_gmail_messages_rejects_missing_connection(
    client, test_user, test_organization, db_session
):
    from app.auth.security import create_access_token
    from app.models.membership import Membership

    db_session.add(
        Membership(
            user_id=test_user.id,
            organization_id=test_organization.id,
            role="owner",
        )
    )
    await db_session.flush()

    token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(minutes=30),
    )
    response = await client.get(
        f"/organizations/{test_organization.id}/gmail/messages",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "No active Gmail connection was found."


@pytest.mark.asyncio
async def test_gmail_messages_rejects_out_of_range_page_size(
    client, test_user, test_organization, db_session
):
    from app.auth.security import create_access_token
    from app.models.membership import Membership

    db_session.add(
        Membership(
            user_id=test_user.id,
            organization_id=test_organization.id,
            role="owner",
        )
    )
    await db_session.flush()

    token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(minutes=30),
    )
    response = await client.get(
        f"/organizations/{test_organization.id}/gmail/messages?max_results=21",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_gmail_messages_returns_metadata_and_updates_last_used(
    client, test_user, test_organization, db_session, monkeypatch
):
    from app.auth.security import create_access_token
    from app.models.gmail_connection import GmailConnection
    from app.models.membership import Membership
    from app.services.gmail_oauth import GMAIL_READONLY_SCOPE
    from app.services import gmail_google_client, gmail_tokens

    db_session.add(
        Membership(
            user_id=test_user.id,
            organization_id=test_organization.id,
            role="owner",
        )
    )
    connection = GmailConnection(
        user_id=test_user.id,
        organization_id=test_organization.id,
        google_email="test@example.com",
        encrypted_refresh_token="mock-encrypted-token",
        scopes=GMAIL_READONLY_SCOPE,
        status="active",
    )
    db_session.add(connection)
    await db_session.flush()

    monkeypatch.setattr(
        gmail_tokens, "decrypt_gmail_token", lambda _: "mock-refresh-token"
    )

    async def fake_refresh(refresh_token):
        assert refresh_token == "mock-refresh-token"
        return "mock-access-token"

    async def fake_list(access_token, *, max_results=20, page_token=None):
        assert access_token == "mock-access-token"
        assert max_results == 2
        assert page_token == "next-page"
        return {
            "messages": [
                {
                    "id": "message-123",
                    "thread_id": "thread-123",
                    "from": "sender@example.com",
                    "subject": "Test subject",
                    "date": "Mon, 26 Oct 2026 10:00:00 +0000",
                    "snippet": "A safe metadata-only preview",
                }
            ],
            "next_page_token": None,
            "result_size_estimate": 1,
        }

    monkeypatch.setattr(
        gmail_google_client, "refresh_gmail_access_token", fake_refresh
    )
    monkeypatch.setattr(
        gmail_google_client, "list_gmail_messages", fake_list
    )

    token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(minutes=30),
    )
    response = await client.get(
        f"/organizations/{test_organization.id}/gmail/messages"
        "?max_results=2&page_token=next-page",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["messages"][0]["subject"] == "Test subject"
    assert response.json()["messages"][0]["id"] == "message-123"
    assert response.json()["result_size_estimate"] == 1

    await db_session.refresh(connection)
    assert connection.last_used_at is not None


@pytest.mark.asyncio
async def test_gmail_messages_rejects_non_readonly_scope(
    client, test_user, test_organization, db_session, monkeypatch
):
    from app.auth.security import create_access_token
    from app.models.gmail_connection import GmailConnection
    from app.models.membership import Membership
    from app.services.gmail_oauth import GMAIL_READONLY_SCOPE
    from app.services import gmail_tokens

    db_session.add(
        Membership(
            user_id=test_user.id,
            organization_id=test_organization.id,
            role="owner",
        )
    )
    db_session.add(
        GmailConnection(
            user_id=test_user.id,
            organization_id=test_organization.id,
            google_email="test@example.com",
            encrypted_refresh_token="mock-encrypted-token",
            scopes=f"{GMAIL_READONLY_SCOPE} https://www.googleapis.com/auth/gmail.send",
            status="active",
        )
    )
    await db_session.flush()

    def should_not_decrypt(_):
        raise AssertionError("Token must not be decrypted for an unsafe scope.")

    monkeypatch.setattr(gmail_tokens, "decrypt_gmail_token", should_not_decrypt)

    token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(minutes=30),
    )
    response = await client.get(
        f"/organizations/{test_organization.id}/gmail/messages",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "read-only scope" in response.json()["detail"]


@pytest.mark.asyncio
async def test_gmail_messages_marks_connection_for_reauthorization(
    client, test_user, test_organization, db_session, monkeypatch
):
    from app.auth.security import create_access_token
    from app.models.gmail_connection import GmailConnection
    from app.models.membership import Membership
    from app.services import gmail_google_client, gmail_tokens
    from app.services.gmail_oauth import GMAIL_READONLY_SCOPE

    db_session.add(
        Membership(
            user_id=test_user.id,
            organization_id=test_organization.id,
            role="owner",
        )
    )
    connection = GmailConnection(
        user_id=test_user.id,
        organization_id=test_organization.id,
        google_email="test@example.com",
        encrypted_refresh_token="mock-encrypted-token",
        scopes=GMAIL_READONLY_SCOPE,
        status="active",
    )
    db_session.add(connection)
    await db_session.flush()

    monkeypatch.setattr(
        gmail_tokens,
        "decrypt_gmail_token",
        lambda _: "revoked-refresh-token",
    )

    async def revoked_refresh_token(_):
        raise gmail_google_client.GmailReauthorizationRequired(
            "Gmail refresh token is invalid or revoked. Reconnect Gmail."
        )

    monkeypatch.setattr(
        gmail_google_client,
        "refresh_gmail_access_token",
        revoked_refresh_token,
    )

    token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(minutes=30),
    )
    response = await client.get(
        f"/organizations/{test_organization.id}/gmail/messages",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Gmail authorization has expired or been revoked. Reconnect Gmail."
    )

    await db_session.refresh(connection)
    assert connection.status == "reauth_required"


@pytest.mark.asyncio
async def test_gmail_import_creates_document_and_queues_ingestion(
    client, test_user, test_organization, db_session, monkeypatch
):
    from app.api.routes import gmail as gmail_routes
    from app.auth.security import create_access_token
    from app.models.gmail_connection import GmailConnection
    from app.models.gmail_import import GmailImport
    from app.models.membership import Membership
    from app.models.document import Document
    from app.services.gmail_oauth import GMAIL_READONLY_SCOPE
    from app.services import gmail_google_client, gmail_tokens
    from sqlalchemy import select

    db_session.add(
        Membership(
            user_id=test_user.id,
            organization_id=test_organization.id,
            role="owner",
        )
    )
    connection = GmailConnection(
        user_id=test_user.id,
        organization_id=test_organization.id,
        google_email="test@example.com",
        encrypted_refresh_token="mock-encrypted-token",
        scopes=GMAIL_READONLY_SCOPE,
        status="active",
    )
    db_session.add(connection)
    await db_session.flush()

    monkeypatch.setattr(
        gmail_routes, "decrypt_gmail_token", lambda _: "mock-refresh-token"
    )

    async def fake_refresh(refresh_token):
        assert refresh_token == "mock-refresh-token"
        return "mock-access-token"

    async def fake_get_message(access_token, message_id):
        assert access_token == "mock-access-token"
        assert message_id == "message-123"
        return {
            "id": "message-123",
            "from": "sender@example.com",
            "subject": "Project notes",
            "date": "Mon, 26 Oct 2026 10:00:00 +0000",
            "body": "The project deadline is Friday.",
            "body_format": "text/plain",
        }

    monkeypatch.setattr(
        gmail_routes, "refresh_gmail_access_token", fake_refresh
    )
    monkeypatch.setattr(
        gmail_routes, "get_gmail_message", fake_get_message
    )

    fake_version_id = uuid.uuid4()
    fake_document_id = uuid.uuid4()

    db_session.add(
        Document(
            id=fake_document_id,
            organization_id=test_organization.id,
            created_by_user_id=test_user.id,
            name="Gmail: Project notes",
        )
    )
    await db_session.flush()

    captured = {}

    async def fake_create_document(**kwargs):
        captured["name"] = kwargs["name"]
        captured["filename"] = kwargs["original_filename"]
        captured["content_type"] = kwargs["content_type"]
        captured["content"] = kwargs["file"].read().decode("utf-8")
        return type(
            "FakeDocumentVersion",
            (),
            {
                "id": fake_version_id,
                "document_id": fake_document_id,
            },
        )()

    monkeypatch.setattr(gmail_routes, "create_document", fake_create_document)

    token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(minutes=30),
    )
    response = await client.post(
        f"/organizations/{test_organization.id}/gmail/messages/message-123/import",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["gmail_message_id"] == "message-123"
    assert payload["document_id"] == str(fake_document_id)
    assert payload["version_id"] == str(fake_version_id)
    assert payload["status"] == "imported"

    assert captured["name"] == "Gmail: Project notes"
    assert captured["filename"].startswith("gmail-")
    assert captured["filename"].endswith(".txt")
    assert captured["content_type"] == "text/plain; charset=utf-8"
    assert "Subject: Project notes" in captured["content"]
    assert "From: sender@example.com" in captured["content"]
    assert "The project deadline is Friday." in captured["content"]

    result = await db_session.execute(
        select(GmailImport).where(
            GmailImport.gmail_connection_id == connection.id,
            GmailImport.gmail_message_id == "message-123",
        )
    )
    imported = result.scalar_one()
    assert imported.status == "imported"
    assert imported.document_id == fake_document_id

    await db_session.refresh(connection)
    assert connection.last_used_at is not None


@pytest.mark.asyncio
async def test_gmail_import_marks_reservation_failed_when_document_creation_fails(
    client, test_user, test_organization, db_session, monkeypatch
):
    from sqlalchemy import select

    from app.auth.security import create_access_token
    from app.models.gmail_connection import GmailConnection
    from app.models.gmail_import import GmailImport
    from app.models.membership import Membership
    from app.services.gmail_oauth import GMAIL_READONLY_SCOPE

    db_session.add(
        Membership(
            user_id=test_user.id,
            organization_id=test_organization.id,
            role="owner",
        )
    )
    connection = GmailConnection(
        user_id=test_user.id,
        organization_id=test_organization.id,
        google_email="test@example.com",
        encrypted_refresh_token="mock-encrypted-token",
        scopes=GMAIL_READONLY_SCOPE,
        status="active",
    )
    db_session.add(connection)
    await db_session.flush()
    connection_id = connection.id

    monkeypatch.setattr(
        gmail_routes,
        "decrypt_gmail_token",
        lambda _: "mock-refresh-token",
    )

    async def fake_refresh(refresh_token):
        assert refresh_token == "mock-refresh-token"
        return "mock-access-token"

    async def fake_get_message(access_token, message_id):
        assert access_token == "mock-access-token"
        assert message_id == "message-failure-123"
        return {
            "id": "message-failure-123",
            "from": "sender@example.com",
            "subject": "Failure test",
            "date": "Mon, 26 Oct 2026 10:00:00 +0000",
            "body": "This import should fail.",
            "body_format": "text/plain",
        }

    async def failing_create_document(**kwargs):
        raise RuntimeError("Simulated document creation failure")

    monkeypatch.setattr(
        gmail_routes, "refresh_gmail_access_token", fake_refresh
    )
    monkeypatch.setattr(
        gmail_routes, "get_gmail_message", fake_get_message
    )
    monkeypatch.setattr(
        gmail_routes, "create_document", failing_create_document
    )

    token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(minutes=30),
    )
    response = await client.post(
        f"/organizations/{test_organization.id}/gmail/messages/"
        "message-failure-123/import",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "The email could not be saved as a DocPilot document."
    )

    result = await db_session.execute(
        select(GmailImport).where(
            GmailImport.gmail_connection_id == connection_id,
            GmailImport.gmail_message_id == "message-failure-123",
        )
    )
    failed_import = result.scalar_one()
    assert failed_import.status == "failed"
    assert failed_import.error_message == (
        "Document creation or import recording failed."
    )
    assert failed_import.document_id is None


@pytest.mark.asyncio
async def test_gmail_import_recovers_when_final_commit_fails(
    client, test_user, test_organization, db_session, monkeypatch
):
    from app.api.routes import gmail as gmail_routes
    from app.auth.security import create_access_token
    from app.models.gmail_connection import GmailConnection
    from app.models.gmail_import import GmailImport
    from app.models.membership import Membership
    from app.models.document import Document
    from app.services.gmail_oauth import GMAIL_READONLY_SCOPE
    from app.services import gmail_google_client, gmail_tokens
    from sqlalchemy import select

    db_session.add(
        Membership(
            user_id=test_user.id,
            organization_id=test_organization.id,
            role="owner",
        )
    )
    connection = GmailConnection(
        user_id=test_user.id,
        organization_id=test_organization.id,
        google_email="test@example.com",
        encrypted_refresh_token="mock-encrypted-token",
        scopes=GMAIL_READONLY_SCOPE,
        status="active",
    )
    db_session.add(connection)
    await db_session.flush()

    monkeypatch.setattr(
        gmail_routes, "decrypt_gmail_token", lambda _: "mock-refresh-token"
    )

    async def fake_refresh(refresh_token):
        assert refresh_token == "mock-refresh-token"
        return "mock-access-token"

    async def fake_get_message(access_token, message_id):
        assert access_token == "mock-access-token"
        assert message_id == "message-recovery-123"
        return {
            "id": "message-recovery-123",
            "from": "sender@example.com",
            "subject": "Project notes",
            "date": "Mon, 26 Oct 2026 10:00:00 +0000",
            "body": "The project deadline is Friday.",
            "body_format": "text/plain",
        }

    monkeypatch.setattr(
        gmail_routes, "refresh_gmail_access_token", fake_refresh
    )
    monkeypatch.setattr(
        gmail_routes, "get_gmail_message", fake_get_message
    )

    fake_version_id = uuid.uuid4()
    fake_document_id = uuid.uuid4()

    db_session.add(
        Document(
            id=fake_document_id,
            organization_id=test_organization.id,
            created_by_user_id=test_user.id,
            name="Gmail: Project notes",
        )
    )
    await db_session.flush()

    captured = {}

    async def fake_create_document(**kwargs):
        captured["name"] = kwargs["name"]
        captured["filename"] = kwargs["original_filename"]
        captured["content_type"] = kwargs["content_type"]
        captured["content"] = kwargs["file"].read().decode("utf-8")
        return type(
            "FakeDocumentVersion",
            (),
            {
                "id": fake_version_id,
                "document_id": fake_document_id,
            },
        )()

    monkeypatch.setattr(gmail_routes, "create_document", fake_create_document)

    original_commit = db_session.commit
    commit_calls = 0

    async def fail_final_commit_once():
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 2:
            raise RuntimeError("Simulated final import commit failure")
        await original_commit()

    monkeypatch.setattr(db_session, "commit", fail_final_commit_once)

    token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(minutes=30),
    )
    response = await client.post(
        f"/organizations/{test_organization.id}/gmail/messages/message-recovery-123/import",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["gmail_message_id"] == "message-recovery-123"
    assert payload["document_id"] == str(fake_document_id)
    assert payload["version_id"] == str(fake_version_id)
    assert payload["status"] == "imported"

    assert captured["name"] == "Gmail: Project notes"
    assert captured["filename"].startswith("gmail-")
    assert captured["filename"].endswith(".txt")
    assert captured["content_type"] == "text/plain; charset=utf-8"
    assert "Subject: Project notes" in captured["content"]
    assert "From: sender@example.com" in captured["content"]
    assert "The project deadline is Friday." in captured["content"]

    result = await db_session.execute(
        select(GmailImport).where(
            GmailImport.gmail_connection_id == connection.id,
            GmailImport.gmail_message_id == "message-recovery-123",
        )
    )
    imported = result.scalar_one()
    assert imported.status == "imported"
    assert imported.document_id == fake_document_id

    await db_session.refresh(connection)
    assert connection.last_used_at is not None


@pytest.mark.asyncio
async def test_gmail_import_logs_reconciliation_when_recovery_commit_fails(
    client, test_user, test_organization, db_session, monkeypatch, caplog
):
    import logging

    from app.auth.security import create_access_token
    from app.models.gmail_connection import GmailConnection
    from app.models.membership import Membership
    from app.services.gmail_oauth import GMAIL_READONLY_SCOPE

    db_session.add(
        Membership(
            user_id=test_user.id,
            organization_id=test_organization.id,
            role="owner",
        )
    )
    connection = GmailConnection(
        user_id=test_user.id,
        organization_id=test_organization.id,
        google_email="test@example.com",
        encrypted_refresh_token="mock-encrypted-token",
        scopes=GMAIL_READONLY_SCOPE,
        status="active",
    )
    db_session.add(connection)
    await db_session.flush()

    monkeypatch.setattr(
        gmail_routes, "decrypt_gmail_token", lambda _: "mock-refresh-token"
    )

    async def fake_refresh(_):
        return "mock-access-token"

    async def fake_get_message(_, message_id):
        return {
            "id": message_id,
            "from": "sender@example.com",
            "subject": "Recovery failure test",
            "date": "Mon, 26 Oct 2026 10:00:00 +0000",
            "body": "Test recovery failure.",
            "body_format": "text/plain",
        }

    monkeypatch.setattr(
        gmail_routes, "refresh_gmail_access_token", fake_refresh
    )
    monkeypatch.setattr(
        gmail_routes, "get_gmail_message", fake_get_message
    )

    from app.models.document import Document

    document_id = uuid.uuid4()
    version_id = uuid.uuid4()

    db_session.add(
        Document(
            id=document_id,
            organization_id=test_organization.id,
            created_by_user_id=test_user.id,
            name="Gmail: Recovery failure test",
        )
    )
    await db_session.flush()

    async def fake_create_document(**_):
        return type(
            "FakeDocumentVersion",
            (),
            {"id": version_id, "document_id": document_id},
        )()

    monkeypatch.setattr(
        gmail_routes, "create_document", fake_create_document
    )

    original_commit = db_session.commit
    commit_calls = 0

    async def fail_final_and_recovery_commits():
        nonlocal commit_calls
        commit_calls += 1

        # Reservation commit succeeds; final import and recovery commits fail.
        if commit_calls in (2, 3):
            raise RuntimeError(f"Simulated commit failure #{commit_calls}")

        await original_commit()

    monkeypatch.setattr(
        db_session, "commit", fail_final_and_recovery_commits
    )

    token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(minutes=30),
    )

    with caplog.at_level(logging.ERROR, logger="app.api.routes.gmail"):
        response = await client.post(
            f"/organizations/{test_organization.id}/gmail/messages/"
            "message-recovery-failure-123/import",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "The email could not be saved as a DocPilot document."
    )
    assert commit_calls == 3
    assert "may need reconciliation" in caplog.text


@pytest.mark.asyncio
async def test_gmail_attachment_import_success_skip_and_failure(
    test_user, test_organization, db_session, monkeypatch
):
    from fastapi import BackgroundTasks
    from sqlalchemy import select

    from app.models.document import Document
    from app.models.gmail_connection import GmailConnection
    from app.models.gmail_import import GmailImport
    from app.models.gmail_import_attachment import GmailImportAttachment
    from app.services.gmail_oauth import GMAIL_READONLY_SCOPE

    connection = GmailConnection(
        user_id=test_user.id,
        organization_id=test_organization.id,
        google_email="attachments@example.com",
        encrypted_refresh_token="unused-in-direct-helper-test",
        scopes=GMAIL_READONLY_SCOPE,
        status="active",
    )
    db_session.add(connection)
    await db_session.flush()

    imported_message = GmailImport(
        gmail_connection_id=connection.id,
        organization_id=test_organization.id,
        gmail_message_id="attachment-test-message",
        sender="sender@example.com",
        subject="Attachment test",
        status="imported",
    )
    db_session.add(imported_message)
    await db_session.flush()
    imported_message_id = imported_message.id

    document_id = uuid.uuid4()
    db_session.add(
        Document(
            id=document_id,
            organization_id=test_organization.id,
            created_by_user_id=test_user.id,
            name="Imported PDF attachment",
        )
    )
    await db_session.flush()

    valid_pdf = b"%PDF-1.7\nTest PDF content\n"

    async def fake_download(
        access_token, message_id, attachment_id, *, max_bytes
    ):
        assert access_token == "test-access-token"
        assert message_id == "attachment-test-message"
        assert max_bytes == 10 * 1024 * 1024

        if attachment_id == "download-fails":
            raise gmail_routes.GmailGoogleAPIError("Simulated download failure")

        assert attachment_id == "pdf-attachment"
        return valid_pdf

    created = []

    async def fake_create_document(**kwargs):
        created.append(
            {
                "filename": kwargs["original_filename"],
                "content_type": kwargs["content_type"],
                "content": kwargs["file"].read(),
            }
        )
        return type(
            "FakeDocumentVersion",
            (),
            {
                "id": uuid.uuid4(),
                "document_id": document_id,
            },
        )()

    async def fake_ingestion_task(version_id):
        return None

    monkeypatch.setattr(
        gmail_routes, "get_gmail_attachment", fake_download
    )
    monkeypatch.setattr(
        gmail_routes, "create_document", fake_create_document
    )

    tasks = BackgroundTasks()
    await gmail_routes._import_gmail_attachments(
        db=db_session,
        storage=None,
        organization_id=test_organization.id,
        user_id=test_user.id,
        gmail_import_id=imported_message.id,
        message_id="attachment-test-message",
        access_token="test-access-token",
        attachments=[
            {
                "attachment_id": "pdf-attachment",
                "filename": "report.pdf",
                "mime_type": "application/pdf",
                "size": len(valid_pdf),
                "is_inline": False,
            },
            {
                "attachment_id": "unsupported-attachment",
                "filename": "program.exe",
                "mime_type": "application/octet-stream",
                "size": 100,
                "is_inline": False,
            },
            {
                "attachment_id": "download-fails",
                "filename": "notes.txt",
                "mime_type": "text/plain",
                "size": None,
                "is_inline": False,
            },
        ],
        background_tasks=tasks,
        ingestion_task=fake_ingestion_task,
    )

    result = await db_session.execute(
        select(GmailImportAttachment).where(
            GmailImportAttachment.gmail_import_id == imported_message_id
        )
    )
    records = {
        record.gmail_attachment_id: record
        for record in result.scalars().all()
    }

    assert set(records) == {
        "pdf-attachment",
        "unsupported-attachment",
        "download-fails",
    }

    assert records["pdf-attachment"].status == "imported"
    assert records["pdf-attachment"].document_id == document_id
    assert records["pdf-attachment"].size_bytes == len(valid_pdf)
    assert records["pdf-attachment"].error_message is None

    assert records["unsupported-attachment"].status == "skipped"
    assert "Unsupported" in records["unsupported-attachment"].error_message

    assert records["download-fails"].status == "failed"
    assert records["download-fails"].error_message

    assert len(created) == 1
    assert created[0]["filename"] == "report.pdf"
    assert created[0]["content_type"] == "application/pdf"
    assert created[0]["content"] == valid_pdf
    assert len(tasks.tasks) == 1


@pytest.mark.asyncio
async def test_gmail_import_succeeds_when_attachment_download_fails(
    client, test_user, test_organization, db_session, monkeypatch
):
    from sqlalchemy import select

    from app.auth.security import create_access_token
    from app.models.gmail_connection import GmailConnection
    from app.models.gmail_import import GmailImport
    from app.models.gmail_import_attachment import GmailImportAttachment
    from app.models.membership import Membership
    from app.services.gmail_oauth import GMAIL_READONLY_SCOPE

    db_session.add(
        Membership(
            user_id=test_user.id,
            organization_id=test_organization.id,
            role="owner",
        )
    )
    connection = GmailConnection(
        user_id=test_user.id,
        organization_id=test_organization.id,
        google_email="route-attachment-test@example.com",
        encrypted_refresh_token="mock-encrypted-token",
        scopes=GMAIL_READONLY_SCOPE,
        status="active",
    )
    db_session.add(connection)
    await db_session.flush()
    connection_id = connection.id

    monkeypatch.setattr(
        gmail_routes, "decrypt_gmail_token", lambda _: "mock-refresh-token"
    )

    async def fake_refresh(refresh_token):
        assert refresh_token == "mock-refresh-token"
        return "mock-access-token"

    async def fake_get_message(access_token, message_id):
        assert access_token == "mock-access-token"
        assert message_id == "message-attachment-failure"
        return {
            "id": message_id,
            "from": "sender@example.com",
            "subject": "Email survives attachment failure",
            "date": "Mon, 26 Oct 2026 10:00:00 +0000",
            "body": "This email should still be imported.",
            "body_format": "text/plain",
            "attachments": [
                {
                    "attachment_id": "failing-pdf",
                    "filename": "report.pdf",
                    "mime_type": "application/pdf",
                    "size": 20,
                    "is_inline": False,
                }
            ],
        }

    fake_document_id = uuid.uuid4()
    fake_version_id = uuid.uuid4()

    from app.models.document import Document

    db_session.add(
        Document(
            id=fake_document_id,
            organization_id=test_organization.id,
            created_by_user_id=test_user.id,
            name="Gmail: Email survives attachment failure",
        )
    )
    await db_session.flush()

    async def fake_create_document(**kwargs):
        # This endpoint call creates the email document. The attachment
        # download will fail before a second document can be created.
        assert kwargs["original_filename"].endswith(".txt")
        assert b"This email should still be imported." in kwargs["file"].read()
        return type(
            "FakeDocumentVersion",
            (),
            {
                "id": fake_version_id,
                "document_id": fake_document_id,
            },
        )()

    async def fake_download(
        access_token, message_id, attachment_id, *, max_bytes
    ):
        assert access_token == "mock-access-token"
        assert message_id == "message-attachment-failure"
        assert attachment_id == "failing-pdf"
        raise gmail_routes.GmailGoogleAPIError(
            "Simulated attachment download failure"
        )

    monkeypatch.setattr(
        gmail_routes, "refresh_gmail_access_token", fake_refresh
    )
    monkeypatch.setattr(
        gmail_routes, "get_gmail_message", fake_get_message
    )
    monkeypatch.setattr(
        gmail_routes, "create_document", fake_create_document
    )
    monkeypatch.setattr(
        gmail_routes, "get_gmail_attachment", fake_download
    )

    token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(minutes=30),
    )
    response = await client.post(
        f"/organizations/{test_organization.id}/gmail/messages/"
        "message-attachment-failure/import",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["gmail_message_id"] == "message-attachment-failure"
    assert payload["document_id"] == str(fake_document_id)
    assert payload["version_id"] == str(fake_version_id)
    assert payload["status"] == "imported"

    imported = await db_session.scalar(
        select(GmailImport).where(
            GmailImport.gmail_connection_id == connection_id,
            GmailImport.gmail_message_id == "message-attachment-failure",
        )
    )
    assert imported is not None
    assert imported.status == "imported"
    assert imported.document_id == fake_document_id

    attachment = await db_session.scalar(
        select(GmailImportAttachment).where(
            GmailImportAttachment.gmail_import_id == imported.id,
            GmailImportAttachment.gmail_attachment_id == "failing-pdf",
        )
    )
    assert attachment is not None
    assert attachment.status == "failed"
    assert "Simulated attachment download failure" in attachment.error_message
