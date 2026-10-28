from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its hash."""
    return password_hash.verify(password, hashed_password)


def _create_token(
    subject: str,
    expires_delta: timedelta,
    token_type: str,
) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + expires_delta
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "token_type": token_type,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(
    subject: str,
    expires_delta: timedelta,
) -> str:
    """Create a signed JWT access token."""
    return _create_token(subject, expires_delta, "access")


def create_refresh_token(
    subject: str,
    expires_delta: timedelta,
) -> str:
    """Create a signed JWT refresh token."""
    return _create_token(subject, expires_delta, "refresh")


def _decode_token(token: str, expected_type: str) -> dict[str, Any]:
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("token_type") != expected_type:
        raise jwt.InvalidTokenError("Invalid token type.")
    return payload


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode only access tokens; reject refresh tokens."""
    return _decode_token(token, "access")


def decode_refresh_token(token: str) -> dict[str, Any]:
    """Decode only refresh tokens; reject access tokens."""
    return _decode_token(token, "refresh")
