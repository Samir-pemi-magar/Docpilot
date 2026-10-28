"""Create and consume short-lived, single-use Gmail OAuth states."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gmail_oauth_state import GmailOAuthState


STATE_TTL = timedelta(minutes=10)


@dataclass(frozen=True, slots=True)
class ConsumedGmailOAuthState:
    """Identity associated with a successfully consumed OAuth state."""

    user_id: UUID
    organization_id: UUID


def _hash_state(state: str) -> str:
    """Return the SHA-256 hex digest of a raw OAuth state token."""
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


async def create_gmail_oauth_state(
    session: AsyncSession,
    *,
    user_id: UUID,
    organization_id: UUID,
) -> str:
    """Persist a hashed, expiring OAuth state and return its raw token."""
    raw_state = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    record = GmailOAuthState(
        state_hash=_hash_state(raw_state),
        user_id=user_id,
        organization_id=organization_id,
        expires_at=now + STATE_TTL,
    )
    session.add(record)
    await session.commit()

    return raw_state


async def consume_gmail_oauth_state(
    session: AsyncSession,
    state: str,
) -> ConsumedGmailOAuthState | None:
    """Atomically consume a valid state once; return None if invalid."""
    if not state or len(state) > 512:
        return None

    now = datetime.now(timezone.utc)

    statement = (
        update(GmailOAuthState)
        .where(
            GmailOAuthState.state_hash == _hash_state(state),
            GmailOAuthState.consumed_at.is_(None),
            GmailOAuthState.expires_at > now,
        )
        .values(consumed_at=now)
        .returning(
            GmailOAuthState.user_id,
            GmailOAuthState.organization_id,
        )
    )

    result = await session.execute(statement)
    consumed = result.one_or_none()
    await session.commit()

    if consumed is None:
        return None

    return ConsumedGmailOAuthState(
        user_id=consumed.user_id,
        organization_id=consumed.organization_id,
    )
