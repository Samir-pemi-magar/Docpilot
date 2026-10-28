"""Build Google OAuth authorization URLs for read-only Gmail access."""

from __future__ import annotations

from urllib.parse import urlencode

from app.core.config import get_settings


GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


class GmailOAuthConfigurationError(RuntimeError):
    """Raised when required Google OAuth settings are missing."""


def build_gmail_authorization_url(state: str) -> str:
    """Build the Google consent URL for read-only Gmail access."""
    settings = get_settings()

    if not settings.gmail_client_id:
        raise GmailOAuthConfigurationError(
            "Google OAuth client ID is not configured."
        )

    if not settings.gmail_redirect_uri:
        raise GmailOAuthConfigurationError(
            "Google OAuth redirect URI is not configured."
        )

    if not state:
        raise ValueError("OAuth state must not be empty.")

    parameters = {
        "client_id": settings.gmail_client_id,
        "redirect_uri": settings.gmail_redirect_uri,
        "response_type": "code",
        "scope": GMAIL_READONLY_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }

    return f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{urlencode(parameters)}"
