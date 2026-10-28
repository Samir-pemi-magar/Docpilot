"""Tests for Gmail OAuth token encryption."""

import pytest
from cryptography.fernet import Fernet

from app.core.config import get_settings
from app.services import gmail_tokens
from app.services.gmail_tokens import (
    GmailTokenEncryptionError,
    decrypt_gmail_token,
    encrypt_gmail_token,
)


def test_token_round_trip():
    token = "test-refresh-token-do-not-use"

    encrypted = encrypt_gmail_token(token)

    assert encrypted != token
    assert decrypt_gmail_token(encrypted) == token


def test_each_encryption_uses_a_fresh_nonce():
    token = "test-refresh-token-do-not-use"

    first = encrypt_gmail_token(token)
    second = encrypt_gmail_token(token)

    assert first != second
    assert decrypt_gmail_token(first) == token
    assert decrypt_gmail_token(second) == token


@pytest.mark.parametrize("token", ["", None])
def test_encrypt_rejects_empty_token(token):
    with pytest.raises(ValueError, match="Token must not be empty"):
        encrypt_gmail_token(token)


@pytest.mark.parametrize("token", ["", None])
def test_decrypt_rejects_empty_token(token):
    with pytest.raises(ValueError, match="Encrypted token must not be empty"):
        decrypt_gmail_token(token)


def test_missing_key_fails_closed(monkeypatch):
    monkeypatch.setattr(
        get_settings(),
        "gmail_token_encryption_key",
        None,
    )

    with pytest.raises(
        GmailTokenEncryptionError,
        match="not configured",
    ):
        encrypt_gmail_token("test-token")


def test_invalid_key_fails_closed(monkeypatch):
    monkeypatch.setattr(
        get_settings(),
        "gmail_token_encryption_key",
        "not-a-valid-fernet-key",
    )

    with pytest.raises(
        GmailTokenEncryptionError,
        match="configuration is invalid",
    ):
        encrypt_gmail_token("test-token")


def test_wrong_key_cannot_decrypt_token(monkeypatch):
    token = "test-refresh-token-do-not-use"
    encrypted = encrypt_gmail_token(token)

    wrong_key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(
        get_settings(),
        "gmail_token_encryption_key",
        wrong_key,
    )

    with pytest.raises(
        GmailTokenEncryptionError,
        match="could not be decrypted",
    ):
        decrypt_gmail_token(encrypted)


def test_tampered_token_cannot_be_decrypted():
    encrypted = encrypt_gmail_token("test-refresh-token-do-not-use")
    tampered = encrypted[:-1] + ("A" if encrypted[-1] != "A" else "B")

    with pytest.raises(
        GmailTokenEncryptionError,
        match="could not be decrypted",
    ):
        decrypt_gmail_token(tampered)
