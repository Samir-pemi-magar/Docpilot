from __future__ import annotations

import jwt
import uuid

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import get_current_user
from app.auth.schemas import (
    DeleteAccountRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.user import User
from app.models.membership import Membership
from app.models.document import Document
from app.models.document_version import DocumentVersion

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)




@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """Create a user account with a securely hashed password."""
    email = str(data.email).lower()

    existing = await db.execute(
        select(User.id).where(User.email == email)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=email,
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.password),
    )
    db.add(user)

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Authenticate a user and return an access token."""
    result = await db.execute(
        select(User).where(User.email == credentials.email)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(
        credentials.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    settings = get_settings()

    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(
            minutes=settings.access_token_expire_minutes
        ),
    )

    refresh_token = create_refresh_token(
        subject=str(user.id),
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Exchange a valid refresh token for a new access/refresh token pair."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token is invalid or expired. Please sign in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_refresh_token(data.refresh_token)
        subject = payload.get("sub")
        user_id = uuid.UUID(subject) if subject else None
    except (jwt.PyJWTError, ValueError, TypeError):
        raise credentials_exception

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    settings = get_settings()
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    refresh_token = create_refresh_token(
        subject=str(user.id),
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the currently authenticated user."""
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    data: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete the current account while preserving shared organization data."""
    if not verify_password(data.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password.",
        )

    owned_org_result = await db.execute(
        select(Membership.organization_id)
        .where(
            Membership.user_id == current_user.id,
            Membership.role == "owner",
        )
        .limit(1)
    )
    if owned_org_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delete organizations you own before deleting your account.",
        )

    try:
        # Preserve documents in organizations shared with other members.
        await db.execute(
            update(Document)
            .where(Document.created_by_user_id == current_user.id)
            .values(created_by_user_id=None)
        )
        await db.execute(
            update(DocumentVersion)
            .where(DocumentVersion.uploaded_by_user_id == current_user.id)
            .values(uploaded_by_user_id=None)
        )
        await db.delete(current_user)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
