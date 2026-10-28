"""Read-only Gmail integration endpoints."""

from __future__ import annotations

import io
import logging
import mimetypes
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_document_ingestion_task, get_storage
from app.auth.authorization import (
    MembershipRole,
    OrganizationAccess,
    get_organization_access,
    require_organization_roles,
)
from app.models.gmail_connection import GmailConnection
from app.models.gmail_import import GmailImport
from app.models.gmail_import_attachment import GmailImportAttachment
from app.services.document import create_document
from app.services.gmail_google_client import (
    GmailGoogleAPIError,
    GmailReauthorizationRequired,
    get_gmail_message,
    get_gmail_attachment,
    refresh_gmail_access_token,
)
from app.services.gmail_tokens import (
    GmailTokenEncryptionError,
    decrypt_gmail_token,
)
from app.services.gmail_oauth import GMAIL_READONLY_SCOPE
from app.core.config import get_settings
from app.db.session import get_db_session
from app.services.gmail_oauth import (
    GmailOAuthConfigurationError,
    build_gmail_authorization_url,
)
from app.services.gmail_oauth_state import create_gmail_oauth_state


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/organizations/{organization_id}/gmail",
    tags=["gmail"],
)


class GmailOAuthStartResponse(BaseModel):
    authorization_url: HttpUrl


@router.post(
    "/oauth/start",
    response_model=GmailOAuthStartResponse,
)
async def start_gmail_oauth(
    organization_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> GmailOAuthStartResponse:
    """Start Google consent for the authenticated user's Gmail account."""
    settings = get_settings()

    if not settings.gmail_client_id or not settings.gmail_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gmail OAuth is not configured.",
        )

    state = await create_gmail_oauth_state(
        db,
        user_id=access.user.id,
        organization_id=organization_id,
    )

    try:
        authorization_url = build_gmail_authorization_url(state)
    except GmailOAuthConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gmail OAuth is not configured.",
        ) from exc

    return GmailOAuthStartResponse(
        authorization_url=authorization_url,
    )


callback_router = APIRouter(tags=["gmail"])


@callback_router.get("/gmail/oauth/callback")
async def gmail_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    """Complete Google's read-only Gmail OAuth flow."""
    from fastapi.responses import RedirectResponse
    from sqlalchemy import select

    from app.models.gmail_connection import GmailConnection
    from app.services.gmail_google_client import (
        GmailGoogleAPIError,
        exchange_code_for_gmail_grant,
    )
    from app.services.gmail_oauth_state import consume_gmail_oauth_state
    from app.services.gmail_tokens import (
        GmailTokenEncryptionError,
        encrypt_gmail_token,
    )

    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired Gmail authorization state.",
        )

    consumed_state = await consume_gmail_oauth_state(db, state)
    if consumed_state is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired Gmail authorization state.",
        )

    if error:
        settings = get_settings()
        frontend_url = settings.frontend_url.rstrip("/")
        return RedirectResponse(
            url=(
                f"{frontend_url}/?gmail=cancelled"
                f"&organization_id={consumed_state.organization_id}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google did not return an authorization code.",
        )

    try:
        grant = await exchange_code_for_gmail_grant(code)
    except GmailGoogleAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Gmail authorization could not be verified.",
        ) from exc

    result = await db.execute(
        select(GmailConnection).where(
            GmailConnection.user_id == consumed_state.user_id,
            GmailConnection.organization_id == consumed_state.organization_id,
        )
    )
    connection = result.scalar_one_or_none()

    if connection is None and not grant.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Google did not provide a refresh token. "
                "Please restart Gmail authorization and grant offline access."
            ),
        )

    try:
        encrypted_refresh_token = (
            encrypt_gmail_token(grant.refresh_token)
            if grant.refresh_token
            else None
        )
    except GmailTokenEncryptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gmail token storage is not configured.",
        ) from exc

    if connection is None:
        connection = GmailConnection(
            user_id=consumed_state.user_id,
            organization_id=consumed_state.organization_id,
            google_email=grant.email,
            encrypted_refresh_token=encrypted_refresh_token,
            scopes=grant.scopes,
            status="active",
        )
        db.add(connection)
    else:
        connection.status = "active"
        connection.scopes = grant.scopes
        if encrypted_refresh_token is not None:
            connection.encrypted_refresh_token = encrypted_refresh_token
            connection.google_email = grant.email

    await db.commit()

    settings = get_settings()
    frontend_url = settings.frontend_url.rstrip("/")
    return RedirectResponse(
        url=(
            f"{frontend_url}/?gmail=connected"
            f"&organization_id={consumed_state.organization_id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/status")
async def get_gmail_status(
    organization_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Return the current user's Gmail connection status for this organization."""
    from sqlalchemy import select

    from app.models.gmail_connection import GmailConnection

    result = await db.execute(
        select(GmailConnection).where(
            GmailConnection.user_id == access.user.id,
            GmailConnection.organization_id == organization_id,
        )
    )
    connection = result.scalar_one_or_none()

    if connection is None:
        return {"connected": False, "status": "not_connected"}

    return {
        "connected": connection.status == "active",
        "status": connection.status,
        "email": connection.google_email,
        "scopes": connection.scopes.split(),
        "created_at": connection.created_at,
        "last_used_at": connection.last_used_at,
    }


@router.get("/messages")
async def get_gmail_messages(
    organization_id: uuid.UUID,
    max_results: int = Query(default=20, ge=1, le=20),
    page_token: str | None = Query(default=None, max_length=4096),
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
):
    """Read a bounded page of Gmail metadata for the connected account."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.models.gmail_connection import GmailConnection
    from app.services.gmail_google_client import (
        GmailGoogleAPIError,
        GmailReauthorizationRequired,
        list_gmail_messages,
        refresh_gmail_access_token,
    )
    from app.services.gmail_oauth import GMAIL_READONLY_SCOPE
    from app.services.gmail_tokens import (
        GmailTokenEncryptionError,
        decrypt_gmail_token,
    )

    if page_token is not None and (
        not page_token.strip() or len(page_token) > 4096
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid Gmail page token.",
        )

    result = await db.execute(
        select(GmailConnection).where(
            GmailConnection.user_id == access.user.id,
            GmailConnection.organization_id == organization_id,
        )
    )
    connection = result.scalar_one_or_none()

    if connection is None or connection.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Gmail connection was found.",
        )

    if set(connection.scopes.split()) != {GMAIL_READONLY_SCOPE}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The Gmail connection does not have the required read-only scope.",
        )

    try:
        refresh_token = decrypt_gmail_token(
            connection.encrypted_refresh_token
        )
        access_token = await refresh_gmail_access_token(refresh_token)
        page = await list_gmail_messages(
            access_token,
            max_results=max_results,
            page_token=page_token,
        )
    except GmailTokenEncryptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gmail token storage is unavailable.",
        ) from exc
    except GmailReauthorizationRequired as exc:
        connection.status = "reauth_required"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gmail authorization has expired or been revoked. Reconnect Gmail.",
        ) from exc
    except GmailGoogleAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Gmail could not be accessed. Try again later.",
        ) from exc

    connection.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    return page



_GMAIL_ATTACHMENT_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".txt", ".md", ".markdown",
}
_GMAIL_ATTACHMENT_MAX_COUNT = 10
_GMAIL_ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024
_GMAIL_ATTACHMENT_TOTAL_MAX_BYTES = 25 * 1024 * 1024
_GMAIL_ATTACHMENT_MAX_TRACKED = 50


def _safe_gmail_attachment_filename(value: object) -> str | None:
    """Return a safe filename, rejecting paths and control characters."""
    if not isinstance(value, str) or not value:
        return None

    if "/" in value or "\\" in value:
        return None

    if re.search(r"[\x00-\x1f\x7f]", value):
        return None

    filename = value.strip()
    if (
        not filename
        or filename in {".", ".."}
        or len(filename) > 255
        or not Path(filename).suffix
    ):
        return None

    return filename


async def _import_gmail_attachments(
    *,
    db,
    storage,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    gmail_import_id: uuid.UUID,
    message_id: str,
    access_token: str,
    attachments: object,
    background_tasks: BackgroundTasks,
    ingestion_task,
) -> None:
    """Import supported Gmail attachments without failing the email import."""
    if not isinstance(attachments, list):
        return

    total_downloaded = 0
    downloaded_count = 0

    # Bound both downloads and tracking work if Gmail returns unusual metadata.
    candidates = attachments[:_GMAIL_ATTACHMENT_MAX_TRACKED]

    for index, item in enumerate(candidates):
        if not isinstance(item, dict):
            continue

        attachment_id = item.get("attachment_id")
        if (
            not isinstance(attachment_id, str)
            or not attachment_id
            or len(attachment_id) > 512
        ):
            logger.warning(
                "Skipping Gmail attachment with invalid ID for import %s.",
                gmail_import_id,
            )
            continue

        filename = _safe_gmail_attachment_filename(item.get("filename"))
        raw_filename = item.get("filename")
        if filename is None:
            # The database requires a filename; use a neutral placeholder
            # while recording why the original name could not be accepted.
            filename = f"attachment-{index + 1}.bin"

        mime_type = item.get("mime_type")
        if not isinstance(mime_type, str) or not mime_type.strip():
            mime_type = mimetypes.guess_type(filename)[0]
        mime_type = mime_type[:255] if mime_type else None

        reported_size = item.get("size")
        if (
            not isinstance(reported_size, int)
            or isinstance(reported_size, bool)
            or reported_size < 0
        ):
            reported_size = None

        existing_result = await db.execute(
            select(GmailImportAttachment).where(
                GmailImportAttachment.gmail_import_id == gmail_import_id,
                GmailImportAttachment.gmail_attachment_id == attachment_id,
            )
        )
        tracking = existing_result.scalar_one_or_none()

        if tracking is not None:
            # Recovery is deliberately limited to attachments misclassified
            # by the previous inline-detection bug. Never retry other records.
            if not (
                tracking.status == "skipped"
                and tracking.error_message == "Inline attachment skipped."
                and tracking.document_id is None
            ):
                logger.debug(
                    "Skipping already tracked Gmail attachment for import %s.",
                    gmail_import_id,
                )
                continue

            tracking.filename = filename
            tracking.content_type = mime_type
            tracking.size_bytes = reported_size
            tracking.status = "pending"
            tracking.error_message = None
            try:
                await db.commit()
                tracking_id = tracking.id
            except Exception:
                await db.rollback()
                logger.exception(
                    "Could not prepare Gmail attachment recovery for import %s.",
                    gmail_import_id,
                )
                continue
        else:
            tracking = GmailImportAttachment(
                gmail_import_id=gmail_import_id,
                gmail_attachment_id=attachment_id,
                filename=filename,
                content_type=mime_type,
                size_bytes=reported_size,
                status="pending",
            )

            try:
                db.add(tracking)
                await db.commit()
                await db.refresh(tracking)
                tracking_id = tracking.id
            except Exception:
                await db.rollback()
                logger.exception(
                    "Could not create Gmail attachment tracking record "
                    "for import %s.",
                    gmail_import_id,
                )
                # Without a durable tracking record, don't download the file.
                continue

        reason = None
        suffix = Path(filename).suffix.lower()

        if raw_filename is not None and _safe_gmail_attachment_filename(
            raw_filename
        ) is None:
            reason = "Unsafe or invalid attachment filename."
        elif item.get("is_inline") is True:
            reason = "Inline attachment skipped."
        elif suffix not in _GMAIL_ATTACHMENT_EXTENSIONS:
            reason = "Unsupported attachment file type."
        elif reported_size is not None and (
            reported_size > _GMAIL_ATTACHMENT_MAX_BYTES
        ):
            reason = "Attachment exceeds the 10 MiB size limit."
        elif downloaded_count >= _GMAIL_ATTACHMENT_MAX_COUNT:
            reason = "Email exceeds the 10-attachment import limit."
        elif reported_size is not None and (
            total_downloaded + reported_size
            > _GMAIL_ATTACHMENT_TOTAL_MAX_BYTES
        ):
            reason = "Email exceeds the 25 MiB attachment data limit."

        if reason:
            try:
                tracking.status = "skipped"
                tracking.error_message = reason
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception(
                    "Could not record skipped Gmail attachment %s.",
                    tracking_id,
                )
            continue

        try:
            content = await get_gmail_attachment(
                access_token,
                message_id,
                attachment_id,
                max_bytes=_GMAIL_ATTACHMENT_MAX_BYTES,
            )

            if len(content) > _GMAIL_ATTACHMENT_MAX_BYTES:
                raise ValueError(
                    "Attachment exceeds the 10 MiB size limit."
                )

            if total_downloaded + len(content) > (
                _GMAIL_ATTACHMENT_TOTAL_MAX_BYTES
            ):
                raise ValueError(
                    "Email exceeds the 25 MiB attachment data limit."
                )

            if reported_size is not None and reported_size != len(content):
                raise ValueError("Attachment size did not match its metadata.")

            # Basic format checks prevent obvious extension/content mismatches.
            if suffix == ".pdf" and not content.startswith(b"%PDF-"):
                raise ValueError("Attachment does not contain a valid PDF header.")

            if suffix in {".docx", ".xlsx"} and not content.startswith(
                b"PK\x03\x04"
            ):
                raise ValueError("Attachment is not a valid ZIP-based Office file.")

            if suffix in {".txt", ".md", ".markdown"}:
                try:
                    content.decode("utf-8-sig")
                except UnicodeDecodeError as exc:
                    raise ValueError(
                        "Text attachment is not valid UTF-8."
                    ) from exc

            total_downloaded += len(content)
            downloaded_count += 1

            attachment_name = f"Gmail attachment: {filename}"[:200]
            version = await create_document(
                db=db,
                storage=storage,
                organization_id=organization_id,
                user_id=user_id,
                name=attachment_name,
                original_filename=filename,
                content_type=mime_type or "application/octet-stream",
                file=io.BytesIO(content),
            )

            # create_document commits independently, so reload the durable
            # tracking record before updating its status and document link.
            tracking = await db.get(GmailImportAttachment, tracking_id)
            if tracking is None:
                raise RuntimeError(
                    "Attachment tracking record disappeared after document creation."
                )

            tracking.document_id = version.document_id
            tracking.size_bytes = len(content)
            tracking.status = "imported"
            tracking.error_message = None
            await db.commit()

            background_tasks.add_task(ingestion_task, version.id)

        except Exception as exc:
            await db.rollback()
            logger.warning(
                "Gmail attachment import failed for import %s, attachment %s: %s",
                gmail_import_id,
                tracking_id,
                str(exc)[:500],
            )

            try:
                tracking = await db.get(
                    GmailImportAttachment,
                    tracking_id,
                )
                if tracking is not None:
                    tracking.status = "failed"
                    tracking.error_message = (
                        str(exc)[:2000] or "Attachment import failed."
                    )
                    await db.commit()
            except Exception:
                await db.rollback()
                logger.exception(
                    "Could not record failure for Gmail attachment %s.",
                    tracking_id,
                )


@router.post(
    "/messages/{message_id}/import",
    status_code=status.HTTP_201_CREATED,
)
async def import_gmail_message(
    organization_id: uuid.UUID,
    message_id: str,
    background_tasks: BackgroundTasks,
    ingestion_task=Depends(get_document_ingestion_task),
    access: OrganizationAccess = Depends(
        require_organization_roles(
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        )
    ),
    db: AsyncSession = Depends(get_db_session),
    storage=Depends(get_storage),
):
    """Import one selected Gmail message into the organization's RAG pipeline."""
    importing_user_id = access.user.id

    if (
        not message_id
        or len(message_id) > 512
        or not message_id.isascii()
        or not all(c.isalnum() or c in "-_" for c in message_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid Gmail message ID.",
        )

    result = await db.execute(
        select(GmailConnection).where(
            GmailConnection.user_id == access.user.id,
            GmailConnection.organization_id == organization_id,
        )
    )
    connection = result.scalar_one_or_none()

    if connection is None or connection.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Gmail connection was found.",
        )

    if set(connection.scopes.split()) != {GMAIL_READONLY_SCOPE}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The Gmail connection does not have the required read-only scope.",
        )

    existing = await db.scalar(
        select(GmailImport).where(
            GmailImport.gmail_connection_id == connection.id,
            GmailImport.gmail_message_id == message_id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Gmail message has already been imported or attempted.",
        )

    try:
        refresh_token = decrypt_gmail_token(
            connection.encrypted_refresh_token
        )
        access_token = await refresh_gmail_access_token(refresh_token)
        message = await get_gmail_message(access_token, message_id)
    except GmailTokenEncryptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gmail token storage is unavailable.",
        ) from exc
    except GmailReauthorizationRequired as exc:
        connection.status = "reauth_required"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gmail authorization has expired or been revoked. Reconnect Gmail.",
        ) from exc
    except GmailGoogleAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Gmail could not retrieve this message.",
        ) from exc

    if message.get("id") != message_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google returned a different Gmail message.",
        )

    subject = message.get("subject") or "(No subject)"
    sender = message.get("from") or ""
    message_date = message.get("date") or ""
    body = message.get("body") or ""

    if not all(isinstance(value, str) for value in (
        subject, sender, message_date, body
    )):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google returned invalid email content.",
        )

    content = (
        f"Subject: {subject}\n"
        f"From: {sender}\n"
        f"Date: {message_date}\n\n"
        f"{body}\n"
    )
    content_bytes = content.encode("utf-8")

    if len(content_bytes) > 1_000_000:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="This email exceeds the 1 MB import limit.",
        )

    connection_id = connection.id
    record = GmailImport(
        gmail_connection_id=connection_id,
        organization_id=organization_id,
        gmail_message_id=message_id,
        sender=sender[:1000] or None,
        subject=subject[:1000],
        message_date=message_date[:255] or None,
        status="pending",
    )
    db.add(record)

    try:
        await db.commit()
        await db.refresh(record)
        record_id = record.id
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Gmail message has already been imported or attempted.",
        ) from exc

    safe_subject = re.sub(r"[\x00-\x1f\x7f]", " ", subject).strip()
    document_name = f"Gmail: {safe_subject}"[:200] or "Gmail email"
    filename = f"gmail-{uuid.uuid4().hex}.txt"

    version = None
    try:
        version = await create_document(
            db=db,
            storage=storage,
            organization_id=organization_id,
            user_id=access.user.id,
            name=document_name,
            original_filename=filename,
            content_type="text/plain; charset=utf-8",
            file=io.BytesIO(content_bytes),
        )

        record.document_id = version.document_id
        record.status = "imported"
        record.error_message = None
        connection.last_used_at = datetime.now(timezone.utc)
        await db.commit()

    except Exception as exc:
        await db.rollback()

        if version is not None:
            # Document creation succeeded. Recover the import link instead
            # of marking a valid document as failed or deleting it.
            try:
                recovered_record = await db.get(GmailImport, record_id)
                if recovered_record is None:
                    raise RuntimeError(
                        "Gmail import reservation disappeared during recovery."
                    )

                recovered_record.document_id = version.document_id
                recovered_record.status = "imported"
                recovered_record.error_message = None

                recovered_connection = await db.get(
                    GmailConnection, connection_id
                )
                if recovered_connection is not None:
                    recovered_connection.last_used_at = datetime.now(
                        timezone.utc
                    )

                await db.commit()
                record = recovered_record
                connection = recovered_connection or connection

                logger.warning(
                    "Recovered Gmail import %s for document %s after "
                    "the final import commit failed.",
                    record_id,
                    version.document_id,
                )
            except Exception:
                await db.rollback()
                logger.exception(
                    "Could not recover Gmail import %s after document "
                    "creation succeeded; document %s may need reconciliation.",
                    record_id,
                    version.document_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "The email could not be saved as a DocPilot document."
                    ),
                ) from exc
        else:
            # No version was returned, so document creation did not
            # complete successfully from this endpoint's perspective.
            try:
                failed_record = await db.get(GmailImport, record_id)
                if failed_record is not None:
                    failed_record.status = "failed"
                    failed_record.error_message = (
                        "Document creation or import recording failed."
                    )
                    await db.commit()
            except Exception:
                await db.rollback()
                logger.exception(
                    "Could not mark Gmail import %s as failed.",
                    record_id,
                )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The email could not be saved as a DocPilot document.",
            ) from exc

    # Save scalar values before attachment processing: its commits/rollbacks
    # may expire ORM objects, and implicit async reloads cause MissingGreenlet.
    imported_record_id = record.id
    imported_record_status = record.status

    # The email is already imported. Attachment failures must not undo it.
    await _import_gmail_attachments(
        db=db,
        storage=storage,
        organization_id=organization_id,
        user_id=importing_user_id,
        gmail_import_id=imported_record_id,
        message_id=message_id,
        access_token=access_token,
        attachments=message.get("attachments", []),
        background_tasks=background_tasks,
        ingestion_task=ingestion_task,
    )

    background_tasks.add_task(ingestion_task, version.id)

    return {
        "id": str(imported_record_id),
        "gmail_message_id": message_id,
        "document_id": str(version.document_id),
        "version_id": str(version.id),
        "status": imported_record_status,
    }
