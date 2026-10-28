"""Encryption helpers for stored Gmail OAuth tokens."""

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class GmailTokenEncryptionError(RuntimeError):
    """Raised when Gmail token encryption or decryption cannot be performed."""


def _get_fernet() -> Fernet:
    """Build the Fernet cipher from the configured encryption key."""
    key = get_settings().gmail_token_encryption_key

    if not key:
        raise GmailTokenEncryptionError(
            "Gmail token encryption is not configured."
        )

    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise GmailTokenEncryptionError(
            "Gmail token encryption configuration is invalid."
        ) from exc


def encrypt_gmail_token(token: str) -> str:
    """Encrypt a Gmail OAuth token for storage."""
    if not token:
        raise ValueError("Token must not be empty.")

    encrypted = _get_fernet().encrypt(token.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt_gmail_token(encrypted_token: str) -> str:
    """Decrypt a previously encrypted Gmail OAuth token."""
    if not encrypted_token:
        raise ValueError("Encrypted token must not be empty.")

    try:
        decrypted = _get_fernet().decrypt(encrypted_token.encode("utf-8"))
    except InvalidToken as exc:
        raise GmailTokenEncryptionError(
            "Gmail token could not be decrypted; check the encryption key "
            "and stored token."
        ) from exc

    return decrypted.decode("utf-8")
