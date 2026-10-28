from types import SimpleNamespace

import httpx
import pytest

from app.services import gmail_google_client as google_client
from app.services.gmail_oauth import GMAIL_READONLY_SCOPE


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "Mock HTTP error",
                request=httpx.Request("GET", "https://example.test"),
                response=httpx.Response(self.status_code),
            )

    def json(self):
        return self._data


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.calls = []
        self.token_response = FakeResponse(
            {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "scope": GMAIL_READONLY_SCOPE,
                "token_type": "Bearer",
            }
        )
        self.profile_response = FakeResponse(
            {"emailAddress": "reader@example.com"}
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.token_response

    async def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.profile_response


@pytest.fixture
def configured_settings(monkeypatch):
    monkeypatch.setattr(
        google_client,
        "get_settings",
        lambda: SimpleNamespace(
            gmail_client_id="mock-client-id",
            gmail_client_secret="mock-client-secret",
            gmail_redirect_uri=(
                "http://127.0.0.1:8000/gmail/oauth/callback"
            ),
        ),
    )


@pytest.mark.asyncio
async def test_exchange_code_returns_gmail_grant(
    monkeypatch, configured_settings
):
    fake_client = FakeAsyncClient()
    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        lambda **kwargs: fake_client,
    )

    grant = await google_client.exchange_code_for_gmail_grant(
        "mock-authorization-code"
    )

    assert grant.email == "reader@example.com"
    assert grant.refresh_token == "mock-refresh-token"
    assert grant.scopes == GMAIL_READONLY_SCOPE

    method, url, kwargs = fake_client.calls[0]
    assert method == "POST"
    assert url == google_client.GOOGLE_TOKEN_ENDPOINT
    assert kwargs["data"]["grant_type"] == "authorization_code"
    assert kwargs["data"]["code"] == "mock-authorization-code"

    method, url, kwargs = fake_client.calls[1]
    assert method == "GET"
    assert url == google_client.GMAIL_PROFILE_ENDPOINT
    assert kwargs["headers"]["Authorization"] == "Bearer mock-access-token"


@pytest.mark.asyncio
async def test_exchange_rejects_missing_readonly_scope(
    monkeypatch, configured_settings
):
    fake_client = FakeAsyncClient()
    fake_client.token_response = FakeResponse(
        {
            "access_token": "mock-access-token",
            "scope": "https://www.googleapis.com/auth/gmail.send",
        }
    )
    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        lambda **kwargs: fake_client,
    )

    with pytest.raises(
        google_client.GmailGoogleAPIError,
        match="read-only scope",
    ):
        await google_client.exchange_code_for_gmail_grant(
            "mock-authorization-code"
        )

    assert len(fake_client.calls) == 1


@pytest.mark.asyncio
async def test_exchange_rejects_invalid_gmail_profile(
    monkeypatch, configured_settings
):
    fake_client = FakeAsyncClient()
    fake_client.profile_response = FakeResponse(
        {"emailAddress": "not-an-email"}
    )
    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        lambda **kwargs: fake_client,
    )

    with pytest.raises(
        google_client.GmailGoogleAPIError,
        match="valid Gmail address",
    ):
        await google_client.exchange_code_for_gmail_grant(
            "mock-authorization-code"
        )


@pytest.mark.asyncio
async def test_exchange_rejects_google_http_error(
    monkeypatch, configured_settings
):
    fake_client = FakeAsyncClient()
    fake_client.token_response = FakeResponse({}, status_code=400)
    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        lambda **kwargs: fake_client,
    )

    with pytest.raises(
        google_client.GmailGoogleAPIError,
        match="verification failed",
    ):
        await google_client.exchange_code_for_gmail_grant(
            "mock-authorization-code"
        )


@pytest.mark.asyncio
async def test_exchange_rejects_missing_configuration(monkeypatch):
    monkeypatch.setattr(
        google_client,
        "get_settings",
        lambda: SimpleNamespace(
            gmail_client_id="",
            gmail_client_secret="",
            gmail_redirect_uri="",
        ),
    )

    with pytest.raises(
        google_client.GmailGoogleAPIError,
        match="configuration is incomplete",
    ):
        await google_client.exchange_code_for_gmail_grant(
            "mock-authorization-code"
        )


@pytest.mark.asyncio
async def test_exchange_rejects_empty_authorization_code():
    with pytest.raises(ValueError, match="must not be empty"):
        await google_client.exchange_code_for_gmail_grant("  ")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scope",
    [
        f"{GMAIL_READONLY_SCOPE} https://www.googleapis.com/auth/gmail.send",
        f"{GMAIL_READONLY_SCOPE} https://www.googleapis.com/auth/gmail.modify",
    ],
)
async def test_exchange_rejects_additional_gmail_permissions(
    monkeypatch,
    configured_settings,
    scope,
):
    fake_client = FakeAsyncClient()
    fake_client.token_response = FakeResponse(
        {
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "scope": scope,
        }
    )
    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        lambda **kwargs: fake_client,
    )

    with pytest.raises(
        google_client.GmailGoogleAPIError,
        match="only the Gmail read-only scope",
    ):
        await google_client.exchange_code_for_gmail_grant(
            "mock-authorization-code"
        )

    assert len(fake_client.calls) == 1


@pytest.mark.asyncio
async def test_refresh_access_token_success(
    monkeypatch, configured_settings
):
    fake_client = FakeAsyncClient()
    fake_client.token_response = FakeResponse(
        {"access_token": "refreshed-access-token", "expires_in": 3600}
    )
    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        lambda **kwargs: fake_client,
    )

    token = await google_client.refresh_gmail_access_token(
        "stored-refresh-token"
    )

    assert token == "refreshed-access-token"
    method, url, kwargs = fake_client.calls[0]
    assert method == "POST"
    assert url == google_client.GOOGLE_TOKEN_ENDPOINT
    assert kwargs["data"]["grant_type"] == "refresh_token"
    assert kwargs["data"]["refresh_token"] == "stored-refresh-token"


@pytest.mark.asyncio
async def test_refresh_access_token_rejects_google_http_error(
    monkeypatch, configured_settings
):
    fake_client = FakeAsyncClient()
    fake_client.token_response = FakeResponse({}, status_code=401)
    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        lambda **kwargs: fake_client,
    )

    with pytest.raises(
        google_client.GmailGoogleAPIError,
        match="could not be refreshed",
    ):
        await google_client.refresh_gmail_access_token("revoked-refresh-token")


@pytest.mark.asyncio
async def test_list_messages_returns_metadata_only(
    monkeypatch,
):
    class MetadataClient:
        def __init__(self, *args, **kwargs):
            self.calls = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            self.calls.append((url, kwargs))

            if url.endswith("/messages"):
                return FakeResponse({
                    "messages": [
                        {"id": "message-1", "threadId": "thread-1"}
                    ],
                    "nextPageToken": "page-2",
                    "resultSizeEstimate": 42,
                })

            return FakeResponse({
                "id": "message-1",
                "snippet": "Preview text",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "sender@example.com"},
                        {"name": "Subject", "value": "Hello"},
                        {"name": "Date", "value": "Mon, 26 Oct 2026 10:00:00 +0000"},
                    ]
                },
            })

    fake_client = MetadataClient()
    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        lambda **kwargs: fake_client,
    )

    result = await google_client.list_gmail_messages(
        "mock-access-token", max_results=5, page_token="page-1"
    )

    assert result["next_page_token"] == "page-2"
    assert result["result_size_estimate"] == 42
    assert result["messages"] == [{
        "id": "message-1",
        "thread_id": "thread-1",
        "from": "sender@example.com",
        "subject": "Hello",
        "date": "Mon, 26 Oct 2026 10:00:00 +0000",
        "snippet": "Preview text",
    }]

    list_url, list_kwargs = fake_client.calls[0]
    assert list_url.endswith("/messages")
    assert list_kwargs["params"] == {
        "maxResults": 5,
        "pageToken": "page-1",
    }

    detail_url, detail_kwargs = fake_client.calls[1]
    assert detail_url.endswith("/messages/message-1")
    assert detail_kwargs["params"]["format"] == "metadata"
    assert detail_kwargs["params"]["metadataHeaders"] == [
        "From", "Subject", "Date"
    ]


@pytest.mark.asyncio
async def test_list_messages_handles_malformed_headers(monkeypatch):
    class MalformedMetadataClient:
        def __init__(self, *args, **kwargs):
            self.calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return FakeResponse({
                    "messages": [{"id": "message-2"}]
                })
            return FakeResponse({
                "snippet": "Safe preview",
                "payload": {"headers": None},
            })

    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        MalformedMetadataClient,
    )

    result = await google_client.list_gmail_messages("mock-access-token")

    assert result["messages"][0]["id"] == "message-2"
    assert result["messages"][0]["from"] is None
    assert result["messages"][0]["subject"] is None
    assert result["messages"][0]["snippet"] == "Safe preview"


@pytest.mark.asyncio
async def test_list_messages_rejects_invalid_page_size():
    with pytest.raises(ValueError, match="between 1 and 20"):
        await google_client.list_gmail_messages(
            "mock-access-token", max_results=21
        )


@pytest.mark.asyncio
async def test_refresh_access_token_requires_reauthorization_on_invalid_grant(
    monkeypatch, configured_settings
):
    fake_client = FakeAsyncClient()
    fake_client.token_response = FakeResponse(
        {"error": "invalid_grant"},
        status_code=400,
    )
    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        lambda **kwargs: fake_client,
    )

    with pytest.raises(
        google_client.GmailReauthorizationRequired,
        match="Reconnect Gmail",
    ):
        await google_client.refresh_gmail_access_token("revoked-refresh-token")


@pytest.mark.asyncio
async def test_refresh_access_token_keeps_temporary_http_errors_generic(
    monkeypatch, configured_settings
):
    fake_client = FakeAsyncClient()
    fake_client.token_response = FakeResponse(
        {"error": "temporarily_unavailable"},
        status_code=503,
    )
    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        lambda **kwargs: fake_client,
    )

    with pytest.raises(
        google_client.GmailGoogleAPIError,
        match="could not be refreshed",
    ) as exc_info:
        await google_client.refresh_gmail_access_token("stored-refresh-token")

    assert not isinstance(
        exc_info.value,
        google_client.GmailReauthorizationRequired,
    )


def test_decode_gmail_body_base64url():
    import base64

    original = "Hello from DocPilot — café"
    encoded = base64.urlsafe_b64encode(original.encode()).decode().rstrip("=")

    assert google_client._decode_gmail_body(encoded) == original


def test_extract_gmail_body_prefers_plain_text():
    import base64

    def encoded(value):
        return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")

    body, body_format = google_client._extract_gmail_body({
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {"data": encoded("Plain email body")},
            },
            {
                "mimeType": "text/html",
                "body": {"data": encoded("<p>HTML email body</p>")},
            },
        ],
    })

    assert body == "Plain email body"
    assert body_format == "text/plain"


def test_extract_gmail_body_strips_html_and_script_content():
    import base64

    html = "<p>Hello <b>DocPilot</b></p><script>secret()</script>"
    encoded = base64.urlsafe_b64encode(html.encode()).decode().rstrip("=")

    body, body_format = google_client._extract_gmail_body({
        "mimeType": "text/html",
        "body": {"data": encoded},
    })

    assert "Hello" in body
    assert "DocPilot" in body
    assert "secret()" not in body
    assert body_format == "text/html"


@pytest.mark.asyncio
async def test_get_gmail_message_returns_decoded_body(monkeypatch):
    import base64

    def encoded(value):
        return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")

    class FullMessageClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            assert url.endswith("/messages/message-123")
            assert kwargs["params"] == {"format": "full"}
            return FakeResponse({
                "id": "message-123",
                "threadId": "thread-123",
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [
                        {"name": "From", "value": "sender@example.com"},
                        {"name": "Subject", "value": "Test email"},
                    ],
                    "body": {"data": encoded("Full email body")},
                },
            })

    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        FullMessageClient,
    )

    result = await google_client.get_gmail_message(
        "mock-access-token",
        "message-123",
    )

    assert result["id"] == "message-123"
    assert result["from"] == "sender@example.com"
    assert result["subject"] == "Test email"
    assert result["body"] == "Full email body"
    assert result["body_format"] == "text/plain"


@pytest.mark.asyncio
async def test_get_gmail_message_rejects_invalid_message_id():
    with pytest.raises(ValueError, match="Invalid Gmail message ID"):
        await google_client.get_gmail_message(
            "mock-access-token",
            "../other-resource",
        )


def test_extract_gmail_attachments_from_nested_mime_parts():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "application/pdf",
                "filename": "report.pdf",
                "body": {
                    "attachmentId": "attachment-pdf",
                    "size": 1234,
                },
            },
            {
                "mimeType": "multipart/related",
                "parts": [
                    {
                        "mimeType": "image/png",
                        "filename": "inline-logo.png",
                        "headers": [
                            {
                                "name": "Content-ID",
                                "value": "<logo>",
                            },
                        ],
                        "body": {
                            "attachmentId": "attachment-image",
                            "size": 42,
                        },
                    },
                ],
            },
            {
                "mimeType": "text/plain",
                "body": {"data": "ZW1haWwgYm9keQ"},
            },
        ],
    }

    attachments = google_client._extract_gmail_attachments(payload)

    assert len(attachments) == 2
    assert attachments[0] == {
        "attachment_id": "attachment-pdf",
        "filename": "report.pdf",
        "mime_type": "application/pdf",
        "size": 1234,
        "is_inline": False,
    }
    assert attachments[1]["filename"] == "inline-logo.png"
    assert attachments[1]["is_inline"] is True



def test_pdf_with_content_id_is_not_classified_as_inline():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "application/pdf",
                "filename": "report.pdf",
                "headers": [
                    {"name": "Content-ID", "value": "<report>"},
                ],
                "body": {
                    "attachmentId": "pdf-with-content-id",
                    "size": 1234,
                },
            },
        ],
    }

    attachments = google_client._extract_gmail_attachments(payload)

    assert len(attachments) == 1
    assert attachments[0]["is_inline"] is False


@pytest.mark.asyncio
async def test_get_gmail_attachment_decodes_bytes(monkeypatch):
    import base64

    content = b"%PDF-1.7 test document"
    encoded = base64.urlsafe_b64encode(content).decode().rstrip("=")

    class AttachmentResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": encoded, "size": len(content)}

    class AttachmentClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            assert url.endswith("/messages/message-123/attachments/attachment-1")
            assert kwargs["headers"]["Authorization"] == "Bearer token"
            return AttachmentResponse()

    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        AttachmentClient,
    )

    result = await google_client.get_gmail_attachment(
        "token",
        "message-123",
        "attachment-1",
    )

    assert result == content


@pytest.mark.asyncio
async def test_get_gmail_attachment_rejects_invalid_message_id():
    with pytest.raises(ValueError, match="Invalid Gmail message ID"):
        await google_client.get_gmail_attachment(
            "token",
            "../invalid",
            "attachment-1",
        )


@pytest.mark.asyncio
async def test_get_gmail_attachment_rejects_invalid_encoding(monkeypatch):
    class AttachmentResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": "%%%not-base64%%%"}

    class AttachmentClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            return AttachmentResponse()

    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        AttachmentClient,
    )

    with pytest.raises(
        google_client.GmailGoogleAPIError,
        match="invalid attachment encoding",
    ):
        await google_client.get_gmail_attachment(
            "token",
            "message-123",
            "attachment-1",
        )


@pytest.mark.asyncio
async def test_get_gmail_attachment_rejects_size_mismatch(monkeypatch):
    import base64

    encoded = base64.urlsafe_b64encode(b"hello").decode().rstrip("=")

    class AttachmentResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": encoded, "size": 999}

    class AttachmentClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            return AttachmentResponse()

    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        AttachmentClient,
    )

    with pytest.raises(
        google_client.GmailGoogleAPIError,
        match="size did not match",
    ):
        await google_client.get_gmail_attachment(
            "token",
            "message-123",
            "attachment-1",
        )


@pytest.mark.asyncio
async def test_get_gmail_attachment_rejects_reported_oversize(
    monkeypatch,
):
    class AttachmentResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": "", "size": 11}

    class AttachmentClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            return AttachmentResponse()

    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        AttachmentClient,
    )

    with pytest.raises(
        google_client.GmailGoogleAPIError,
        match="exceeds the maximum allowed size",
    ):
        await google_client.get_gmail_attachment(
            "token",
            "message-123",
            "attachment-1",
            max_bytes=10,
        )


@pytest.mark.asyncio
async def test_get_gmail_attachment_rejects_encoded_oversize(
    monkeypatch,
):
    import base64

    encoded = base64.urlsafe_b64encode(b"x" * 11).decode().rstrip("=")

    class AttachmentResponse:
        def raise_for_status(self):
            return None

        def json(self):
            # No reported size: the encoded payload must still be checked.
            return {"data": encoded}

    class AttachmentClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            return AttachmentResponse()

    monkeypatch.setattr(
        google_client.httpx,
        "AsyncClient",
        AttachmentClient,
    )

    with pytest.raises(
        google_client.GmailGoogleAPIError,
        match="exceeds the maximum allowed size",
    ):
        await google_client.get_gmail_attachment(
            "token",
            "message-123",
            "attachment-1",
            max_bytes=10,
        )
