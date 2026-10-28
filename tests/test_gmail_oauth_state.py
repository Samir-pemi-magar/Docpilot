"""Tests for single-use Gmail OAuth state management."""

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.gmail_oauth_state import GmailOAuthState
from app.services.gmail_oauth_state import (
    STATE_TTL,
    consume_gmail_oauth_state,
    create_gmail_oauth_state,
)


@pytest.mark.asyncio
async def test_create_state_stores_hash_not_raw_token(db_session, test_user, test_organization):
    organization_id = test_organization.id

    raw_state = await create_gmail_oauth_state(
        db_session,
        user_id=test_user.id,
        organization_id=organization_id,
    )

    assert raw_state
    assert len(raw_state) >= 32

    stored = await db_session.get(
        GmailOAuthState,
        hashlib.sha256(raw_state.encode("utf-8")).hexdigest(),
    )

    assert stored is not None
    assert stored.state_hash != raw_state
    assert stored.user_id == test_user.id
    assert stored.organization_id == organization_id
    assert stored.consumed_at is None

    remaining = await db_session.execute(
        select(GmailOAuthState).where(
            GmailOAuthState.state_hash == raw_state
        )
    )
    assert remaining.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_created_state_has_ten_minute_lifetime(db_session, test_user, test_organization):
    organization_id = test_organization.id

    raw_state = await create_gmail_oauth_state(
        db_session,
        user_id=test_user.id,
        organization_id=organization_id,
    )

    stored = await db_session.get(
        GmailOAuthState,
        hashlib.sha256(raw_state.encode("utf-8")).hexdigest(),
    )

    assert stored is not None
    now = datetime.now(timezone.utc)
    assert stored.expires_at > now
    assert stored.expires_at <= now + STATE_TTL + timedelta(seconds=2)


@pytest.mark.asyncio
async def test_each_created_state_is_different(db_session, test_user, test_organization):
    organization_id = test_organization.id

    first = await create_gmail_oauth_state(
        db_session,
        user_id=test_user.id,
        organization_id=organization_id,
    )
    second = await create_gmail_oauth_state(
        db_session,
        user_id=test_user.id,
        organization_id=organization_id,
    )

    assert first != second


@pytest.mark.asyncio
async def test_consume_returns_initiating_identity_once(
    db_session,
    test_user,
    test_organization,
):
    organization_id = test_organization.id

    raw_state = await create_gmail_oauth_state(
        db_session,
        user_id=test_user.id,
        organization_id=organization_id,
    )

    consumed = await consume_gmail_oauth_state(db_session, raw_state)

    assert consumed is not None
    assert consumed.user_id == test_user.id
    assert consumed.organization_id == organization_id

    stored = await db_session.get(
        GmailOAuthState,
        hashlib.sha256(raw_state.encode("utf-8")).hexdigest(),
    )
    assert stored is not None
    assert stored.consumed_at is not None


@pytest.mark.asyncio
async def test_state_cannot_be_consumed_twice(db_session, test_user, test_organization):
    raw_state = await create_gmail_oauth_state(
        db_session,
        user_id=test_user.id,
        organization_id=test_organization.id,
    )

    first = await consume_gmail_oauth_state(db_session, raw_state)
    second = await consume_gmail_oauth_state(db_session, raw_state)

    assert first is not None
    assert second is None


@pytest.mark.asyncio
async def test_unknown_state_is_rejected(db_session):
    assert (
        await consume_gmail_oauth_state(
            db_session,
            "unknown-state-value",
        )
        is None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["", "x" * 513])
async def test_empty_or_oversized_state_is_rejected(db_session, state):
    assert await consume_gmail_oauth_state(db_session, state) is None


@pytest.mark.asyncio
async def test_expired_state_is_rejected(db_session, test_user, test_organization):
    raw_state = await create_gmail_oauth_state(
        db_session,
        user_id=test_user.id,
        organization_id=test_organization.id,
    )
    state_hash = hashlib.sha256(raw_state.encode("utf-8")).hexdigest()

    stored = await db_session.get(GmailOAuthState, state_hash)
    assert stored is not None

    stored.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.flush()

    consumed = await consume_gmail_oauth_state(db_session, raw_state)

    assert consumed is None
    assert stored.consumed_at is None
