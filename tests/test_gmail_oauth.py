"""Tests for Google Gmail OAuth URL construction."""

from urllib.parse import parse_qs, urlparse

import pytest

from app.services import gmail_oauth
from app.services.gmail_oauth import (
    GMAIL_READONLY_SCOPE,
    GOOGLE_AUTHORIZATION_ENDPOINT,
    GmailOAuthConfigurationError,
    build_gmail_authorization_url,
)


def test_authorization_url_contains_readonly_scope(monkeypatch):
    class FakeSettings:
        gmail_client_id = "test-client-id.apps.googleusercontent.com"
        gmail_redirect_uri = "http://127.0.0.1:8000/gmail/oauth/callback"

    monkeypatch.setattr(gmail_oauth, "get_settings", lambda: FakeSettings())

    url = build_gmail_authorization_url("random-state-value")
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == (
        GOOGLE_AUTHORIZATION_ENDPOINT
    )
    assert params["client_id"] == [
        "test-client-id.apps.googleusercontent.com"
    ]
    assert params["redirect_uri"] == [
        "http://127.0.0.1:8000/gmail/oauth/callback"
    ]
    assert params["response_type"] == ["code"]
    assert params["scope"] == [GMAIL_READONLY_SCOPE]
    assert params["access_type"] == ["offline"]
    assert params["prompt"] == ["consent"]
    assert params["include_granted_scopes"] == ["true"]
    assert params["state"] == ["random-state-value"]


def test_authorization_url_encodes_state(monkeypatch):
    class FakeSettings:
        gmail_client_id = "client-id"
        gmail_redirect_uri = "http://127.0.0.1:8000/gmail/oauth/callback"

    monkeypatch.setattr(gmail_oauth, "get_settings", lambda: FakeSettings())

    state = "state/with special+characters"
    url = build_gmail_authorization_url(state)

    assert parse_qs(urlparse(url).query)["state"] == [state]


@pytest.mark.parametrize(
    ("client_id", "redirect_uri"),
    [
        (None, "http://127.0.0.1:8000/gmail/oauth/callback"),
        ("client-id", None),
    ],
)
def test_missing_required_configuration_is_rejected(
    monkeypatch,
    client_id,
    redirect_uri,
):
    class FakeSettings:
        gmail_client_id = client_id
        gmail_redirect_uri = redirect_uri

    monkeypatch.setattr(gmail_oauth, "get_settings", lambda: FakeSettings())

    with pytest.raises(GmailOAuthConfigurationError):
        build_gmail_authorization_url("state-value")


def test_empty_state_is_rejected(monkeypatch):
    class FakeSettings:
        gmail_client_id = "client-id"
        gmail_redirect_uri = "http://127.0.0.1:8000/gmail/oauth/callback"

    monkeypatch.setattr(gmail_oauth, "get_settings", lambda: FakeSettings())

    with pytest.raises(ValueError, match="state must not be empty"):
        build_gmail_authorization_url("")
