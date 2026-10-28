from __future__ import annotations

import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authorization import (
    OrganizationAccess,
    get_organization_access,
)
from app.db.session import get_db_session
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.chat_pdf_export import generate_chat_answer_pdf
from app.schemas.conversation import (
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationSummary,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/conversations",
    tags=["conversations"],
)


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    organization_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> ConversationListResponse:
    """List the current user's conversations within an organization."""
    owner_filter = (
        Conversation.organization_id == organization_id,
        Conversation.created_by_user_id == access.user.id,
    )

    total = await db.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(*owner_filter)
    )

    message_count = (
        select(func.count(Message.id))
        .where(Message.conversation_id == Conversation.id)
        .correlate(Conversation)
        .scalar_subquery()
    )

    result = await db.execute(
        select(Conversation, message_count.label("message_count"))
        .where(*owner_filter)
        .order_by(
            Conversation.updated_at.desc(),
            Conversation.created_at.desc(),
            Conversation.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    items = [
        ConversationSummary(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=count,
        )
        for conversation, count in result.all()
    ]

    return ConversationListResponse(
        items=items,
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
)
async def get_conversation(
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> ConversationDetailResponse:
    """Get one conversation and its messages, if owned by the current user."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == organization_id,
            Conversation.created_by_user_id == access.user.id,
        )
    )
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    message_result = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(
            Message.created_at.asc(),
            Message.role.desc(),
            Message.id.asc(),
        )
    )
    messages = list(message_result)

    count = len(messages)

    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=count,
        messages=messages,
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a conversation owned by the current user in this organization."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == organization_id,
            Conversation.created_by_user_id == access.user.id,
        )
    )
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    await db.delete(conversation)
    await db.commit()


@router.get(
    "/{conversation_id}/messages/{message_id}/pdf",
    response_class=StreamingResponse,
)
async def download_chat_answer_pdf(
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Download a PDF for an assistant answer in the current user's conversation."""
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == organization_id,
            Conversation.created_by_user_id == access.user.id,
        )
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    message_result = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(
            Message.created_at.asc(),
            Message.role.desc(),
            Message.id.asc(),
        )
    )
    messages = list(message_result)

    selected_index = next(
        (
            index
            for index, message in enumerate(messages)
            if message.id == message_id and message.role == "assistant"
        ),
        None,
    )

    if selected_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant message not found.",
        )

    question = "Question not available."
    for previous in reversed(messages[:selected_index]):
        if previous.role == "user":
            question = previous.content
            break

    message = messages[selected_index]
    pdf_bytes = generate_chat_answer_pdf(
        question=question,
        answer=message.content,
        sources=message.sources or [],
        conversation_id=str(conversation.id),
        message_id=str(message.id),
    )

    filename = f"docpilot-answer-{message.id}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
