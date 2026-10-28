"""HTTP client helpers for Google's read-only Gmail OAuth flow."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.services.gmail_oauth import GMAIL_READONLY_SCOPE


GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GMAIL_PROFILE_ENDPOINT = (
    "https://gmail.googleapis.com/gmail/v1/users/me/profile"
)


class GmailGoogleAPIError(RuntimeError):
    """Raised when Google's OAuth or account API cannot be used safely."""


class GmailReauthorizationRequired(GmailGoogleAPIError):
    """Raised when Google rejects a stored refresh token permanently."""


@dataclass(frozen=True, slots=True)
class GmailOAuthGrant:
    """Validated token and account data returned by Google."""

    email: str
    refresh_token: str | None
    scopes: str


async def exchange_code_for_gmail_grant(
    code: str,
) -> GmailOAuthGrant:
    """Exchange an OAuth code and retrieve the authorized Gmail account."""
    if not code or not code.strip():
        raise ValueError("OAuth authorization code must not be empty.")

    settings = get_settings()

    if not all(
        (
            settings.gmail_client_id,
            settings.gmail_client_secret,
            settings.gmail_redirect_uri,
        )
    ):
        raise GmailGoogleAPIError(
            "Google OAuth client configuration is incomplete."
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_response = await client.post(
                GOOGLE_TOKEN_ENDPOINT,
                data={
                    "code": code,
                    "client_id": settings.gmail_client_id,
                    "client_secret": settings.gmail_client_secret,
                    "redirect_uri": settings.gmail_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            token_data = token_response.json()

            if not isinstance(token_data, dict):
                raise GmailGoogleAPIError(
                    "Google returned an invalid token response."
                )

            access_token = token_data.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise GmailGoogleAPIError(
                    "Google did not return an access token."
                )

            granted_scope = token_data.get("scope", "")
            if not isinstance(granted_scope, str):
                raise GmailGoogleAPIError(
                    "Google returned an invalid scope response."
                )

            granted_scopes = set(granted_scope.split())
            if granted_scopes != {GMAIL_READONLY_SCOPE}:
                raise GmailGoogleAPIError(
                    "Google must grant only the Gmail read-only scope."
                )

            profile_response = await client.get(
                GMAIL_PROFILE_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            profile_response.raise_for_status()
            profile_data = profile_response.json()

    except GmailGoogleAPIError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise GmailGoogleAPIError(
            "Google OAuth verification failed."
        ) from exc

    if not isinstance(profile_data, dict):
        raise GmailGoogleAPIError(
            "Google returned an invalid Gmail profile."
        )

    email = profile_data.get("emailAddress")
    if (
        not isinstance(email, str)
        or not email
        or "@" not in email
        or email.startswith("@")
        or email.endswith("@")
    ):
        raise GmailGoogleAPIError(
            "Google did not return a valid Gmail address."
        )

    refresh_token = token_data.get("refresh_token")
    if refresh_token is not None and (
        not isinstance(refresh_token, str) or not refresh_token
    ):
        raise GmailGoogleAPIError(
            "Google returned an invalid refresh token."
        )

    return GmailOAuthGrant(
        email=email,
        refresh_token=refresh_token,
        scopes=" ".join(sorted(granted_scopes)),
    )


async def refresh_gmail_access_token(refresh_token: str) -> str:
    """Exchange a stored refresh token for a short-lived access token."""
    if not refresh_token or not refresh_token.strip():
        raise ValueError("Gmail refresh token must not be empty.")

    settings = get_settings()
    if not all(
        (
            settings.gmail_client_id,
            settings.gmail_client_secret,
        )
    ):
        raise GmailGoogleAPIError(
            "Google OAuth client configuration is incomplete."
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                GOOGLE_TOKEN_ENDPOINT,
                data={
                    "client_id": settings.gmail_client_id,
                    "client_secret": settings.gmail_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            if response.status_code >= 400:
                error_code = None
                try:
                    error_data = response.json()
                    if isinstance(error_data, dict):
                        error_code = error_data.get("error")
                except ValueError:
                    pass

                if error_code == "invalid_grant":
                    raise GmailReauthorizationRequired(
                        "Gmail refresh token is invalid or revoked. "
                        "Reconnect Gmail."
                    )

                response.raise_for_status()

            data = response.json()

    except GmailReauthorizationRequired:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise GmailGoogleAPIError(
            "Gmail access token could not be refreshed."
        ) from exc

    if not isinstance(data, dict):
        raise GmailGoogleAPIError(
            "Google returned an invalid token response."
        )

    access_token = data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise GmailGoogleAPIError(
            "Google did not return an access token."
        )

    return access_token


async def list_gmail_messages(
    access_token: str,
    *,
    max_results: int = 20,
    page_token: str | None = None,
) -> dict:
    """List a bounded page of Gmail message metadata without reading bodies."""
    if not access_token:
        raise ValueError("Gmail access token must not be empty.")

    if not 1 <= max_results <= 20:
        raise ValueError("max_results must be between 1 and 20.")

    headers = {"Authorization": f"Bearer {access_token}"}
    parameters: dict[str, str | int] = {
        "maxResults": max_results,
    }
    if page_token:
        parameters["pageToken"] = page_token

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers=headers,
                params=parameters,
            )
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict):
                raise GmailGoogleAPIError(
                    "Google returned an invalid message list."
                )

            raw_messages = data.get("messages", [])
            if not isinstance(raw_messages, list):
                raise GmailGoogleAPIError(
                    "Google returned an invalid message list."
                )

            messages = []
            for item in raw_messages:
                if not isinstance(item, dict):
                    continue

                message_id = item.get("id")
                if not isinstance(message_id, str) or not message_id:
                    continue

                # Metadata only: deliberately do not request message bodies.
                detail_response = await client.get(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/"
                    + message_id,
                    headers=headers,
                    params={
                        "format": "metadata",
                        "metadataHeaders": ["From", "Subject", "Date"],
                    },
                )
                detail_response.raise_for_status()
                detail = detail_response.json()

                if not isinstance(detail, dict):
                    continue

                payload = detail.get("payload", {})
                header_list = (
                    payload.get("headers", [])
                    if isinstance(payload, dict)
                    else []
                )
                if not isinstance(header_list, list):
                    header_list = []

                header_map = {
                    header["name"].lower(): header["value"]
                    for header in header_list
                    if isinstance(header, dict)
                    and isinstance(header.get("name"), str)
                    and isinstance(header.get("value"), str)
                }

                snippet = detail.get("snippet", "")
                messages.append(
                    {
                        "id": message_id,
                        "thread_id": item.get("threadId"),
                        "from": header_map.get("from"),
                        "subject": header_map.get("subject"),
                        "date": header_map.get("date"),
                        "snippet": snippet if isinstance(snippet, str) else "",
                    }
                )

    except GmailGoogleAPIError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise GmailGoogleAPIError(
            "Gmail messages could not be retrieved."
        ) from exc

    next_page_token = data.get("nextPageToken")
    return {
        "messages": messages,
        "next_page_token": (
            next_page_token if isinstance(next_page_token, str) else None
        ),
        "result_size_estimate": data.get("resultSizeEstimate", 0),
    }


def _decode_gmail_body(data: str) -> str:
    """Decode a Gmail Base64URL-encoded MIME body safely."""
    import base64
    import binascii

    if not data:
        return ""

    try:
        padded = data + "=" * (-len(data) % 4)
        decoded = base64.urlsafe_b64decode(padded)
        return decoded.decode("utf-8", errors="replace")
    except (ValueError, binascii.Error):
        return ""



def _extract_gmail_attachments(payload: dict) -> list[dict]:
    """Collect named Gmail attachment metadata without downloading file data."""
    attachments: list[dict] = []

    def visit(part: dict) -> None:
        filename = part.get("filename")
        body = part.get("body", {})
        headers = part.get("headers", [])

        if not isinstance(body, dict):
            body = {}

        header_map = {
            item["name"].lower(): item["value"]
            for item in headers
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and isinstance(item.get("value"), str)
        } if isinstance(headers, list) else {}

        attachment_id = body.get("attachmentId")
        if isinstance(filename, str) and filename.strip():
            if isinstance(attachment_id, str) and attachment_id:
                size = body.get("size")
                if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                    size = None

                disposition = header_map.get("content-disposition", "").lower()
                content_id = header_map.get("content-id", "")
                mime_type = part.get("mimeType")
                is_inline = disposition.strip().startswith("inline") or (
                    isinstance(mime_type, str)
                    and mime_type.lower().startswith("image/")
                    and bool(content_id.strip())
                )
                attachments.append({
                    "attachment_id": attachment_id,
                    "filename": filename,
                    "mime_type": mime_type,
                    "size": size,
                    "is_inline": is_inline,
                })

        children = part.get("parts", [])
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    visit(child)

    visit(payload)
    return attachments

def _extract_gmail_body(payload: dict) -> tuple[str, str]:
    """Extract readable plain-text content, falling back to HTML text."""
    import re
    from html import unescape

    plain_parts: list[str] = []
    html_parts: list[str] = []

    def visit(part: dict) -> None:
        mime_type = part.get("mimeType", "")
        body = part.get("body", {})
        if isinstance(body, dict):
            data = body.get("data")
            if isinstance(data, str) and data:
                decoded = _decode_gmail_body(data)
                if mime_type == "text/plain":
                    plain_parts.append(decoded)
                elif mime_type == "text/html":
                    html_parts.append(decoded)

        parts = part.get("parts", [])
        if isinstance(parts, list):
            for child in parts:
                if isinstance(child, dict):
                    visit(child)

    visit(payload)

    if plain_parts:
        return "\n\n".join(plain_parts).strip(), "text/plain"

    if html_parts:
        html = "\n\n".join(html_parts)
        # Remove non-content blocks before stripping tags.
        html = re.sub(
            r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>",
            " ",
            html,
        )
        html = re.sub(r"(?i)<br\s*/?>|</p\s*>|</div\s*>|</li\s*>", "\n", html)
        text = re.sub(r"(?s)<[^>]*>", " ", html)
        text = unescape(text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        return text.strip(), "text/html"

    return "", "text/plain"


async def get_gmail_message(
    access_token: str,
    message_id: str,
) -> dict:
    """Retrieve one full Gmail message and extract readable body text."""
    if not access_token or not access_token.strip():
        raise ValueError("Gmail access token must not be empty.")

    if (
        not message_id
        or len(message_id) > 512
        or not all(c.isalnum() or c in "-_" for c in message_id)
    ):
        raise ValueError("Invalid Gmail message ID.")

    url = (
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/"
        + message_id
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                params={"format": "full"},
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise GmailGoogleAPIError(
            "Gmail message could not be retrieved."
        ) from exc

    if not isinstance(data, dict):
        raise GmailGoogleAPIError("Google returned an invalid message.")

    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise GmailGoogleAPIError("Google returned an invalid message payload.")

    headers = payload.get("headers", [])
    if not isinstance(headers, list):
        headers = []

    header_map = {
        item["name"].lower(): item["value"]
        for item in headers
        if isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and isinstance(item.get("value"), str)
    }

    body, body_format = _extract_gmail_body(payload)

    return {
        "id": data.get("id", message_id),
        "thread_id": data.get("threadId"),
        "from": header_map.get("from"),
        "to": header_map.get("to"),
        "subject": header_map.get("subject"),
        "date": header_map.get("date"),
        "body": body,
        "body_format": body_format,
        "attachments": _extract_gmail_attachments(payload),
    }



async def get_gmail_attachment(
    access_token: str,
    message_id: str,
    attachment_id: str,
    *,
    max_bytes: int = 10 * 1024 * 1024,
) -> bytes:
    """Download and strictly decode one Gmail attachment payload."""
    import base64
    import binascii
    from urllib.parse import quote

    if not access_token or not access_token.strip():
        raise ValueError("Gmail access token must not be empty.")

    if (
        not message_id
        or len(message_id) > 512
        or not message_id.isascii()
        or not all(c.isalnum() or c in "-_" for c in message_id)
    ):
        raise ValueError("Invalid Gmail message ID.")

    if (
        not isinstance(attachment_id, str)
        or not attachment_id
        or len(attachment_id) > 2048
        or any(ord(c) < 32 or ord(c) == 127 for c in attachment_id)
    ):
        raise ValueError("Invalid Gmail attachment ID.")

    if (
        isinstance(max_bytes, bool)
        or not isinstance(max_bytes, int)
        or max_bytes < 0
    ):
        raise ValueError(
            "Attachment max_bytes must be a non-negative integer."
        )

    url = (
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/"
        + message_id
        + "/attachments/"
        + quote(attachment_id, safe="")
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise GmailGoogleAPIError(
            "Gmail attachment could not be retrieved."
        ) from exc

    if not isinstance(data, dict):
        raise GmailGoogleAPIError(
            "Google returned an invalid attachment response."
        )

    encoded = data.get("data")
    if not isinstance(encoded, str):
        raise GmailGoogleAPIError(
            "Google returned an invalid attachment payload."
        )

    reported_size = data.get("size")
    if isinstance(reported_size, int) and not isinstance(
        reported_size, bool
    ):
        if reported_size < 0:
            raise GmailGoogleAPIError(
                "Google returned an invalid attachment size."
            )
        if reported_size > max_bytes:
            raise GmailGoogleAPIError(
                "Gmail attachment exceeds the maximum allowed size."
            )

    # Reject oversized Base64 data before allocating the decoded bytes.
    max_encoded_chars = 4 * ((max_bytes + 2) // 3)
    if len(encoded) > max_encoded_chars:
        raise GmailGoogleAPIError(
            "Gmail attachment exceeds the maximum allowed size."
        )

    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        decoded = base64.b64decode(
            padded,
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, binascii.Error) as exc:
        raise GmailGoogleAPIError(
            "Google returned an invalid attachment encoding."
        ) from exc

    if len(decoded) > max_bytes:
        raise GmailGoogleAPIError(
            "Gmail attachment exceeds the maximum allowed size."
        )

    if (
        isinstance(reported_size, int)
        and not isinstance(reported_size, bool)
        and reported_size != len(decoded)
    ):
        raise GmailGoogleAPIError(
            "Gmail attachment size did not match its payload."
        )

    return decoded
