from __future__ import annotations

import uuid

import pytest
import pymupdf
from sqlalchemy import select

from app.auth.security import hash_password
from app.models.conversation import Conversation
from app.models.membership import Membership
from app.models.message import Message
from app.models.organization import Organization
from app.models.user import User


PASSWORD = "TestPassword123!"


async def create_user(db_session, email: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password(PASSWORD),
        full_name="PDF Export Test User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def create_organization(db_session, owner: User) -> Organization:
    organization = Organization(
        name="PDF Export Test Organization",
        slug=f"pdf-test-{uuid.uuid4().hex[:12]}",
    )
    db_session.add(organization)
    await db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=owner.id,
            role="owner",
        )
    )
    await db_session.flush()
    return organization


async def login(client, email: str) -> str:
    response = await client.post(
        "/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_download_chat_answer_pdf_contains_question_answer_and_sources(
    client, db_session
):
    user = await create_user(db_session, "pdf-export-owner@example.com")
    organization = await create_organization(db_session, user)

    conversation = Conversation(
        organization_id=organization.id,
        created_by_user_id=user.id,
        title="PDF export test",
    )
    db_session.add(conversation)
    await db_session.flush()

    db_session.add_all(
        [
            Message(
                conversation_id=conversation.id,
                role="user",
                content="What is the refund policy?",
            ),
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content="**Refunds** are available within seven days.",
                sources=[
                    {
                        "document_name": "Refund Policy",
                        "chunk_index": 2,
                        "text": "Customers may request a refund within seven days.",
                    }
                ],
            ),
        ]
    )
    await db_session.flush()

    assistant = await db_session.scalar(
        select(Message).where(
            Message.conversation_id == conversation.id,
            Message.role == "assistant",
        )
    )
    token = await login(client, user.email)

    response = await client.get(
        f"/organizations/{organization.id}/conversations/"
        f"{conversation.id}/messages/{assistant.id}/pdf",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")

    document = pymupdf.open(stream=response.content, filetype="pdf")
    extracted_text = "\n".join(page.get_text() for page in document)
    document.close()

    assert "What is the refund policy?" in extracted_text
    assert "Refunds are available within seven days." in extracted_text
    assert "Refund Policy" in extracted_text
    assert "Customers may request a refund within seven days." in extracted_text


@pytest.mark.asyncio
async def test_user_cannot_download_another_users_chat_pdf(client, db_session):
    owner = await create_user(db_session, "pdf-private-owner@example.com")
    member = await create_user(db_session, "pdf-private-member@example.com")
    organization = await create_organization(db_session, owner)

    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=member.id,
            role="member",
        )
    )
    conversation = Conversation(
        organization_id=organization.id,
        created_by_user_id=owner.id,
        title="Private conversation",
    )
    db_session.add(conversation)
    await db_session.flush()

    assistant = Message(
        conversation_id=conversation.id,
        role="assistant",
        content="Private answer",
        sources=[],
    )
    db_session.add(assistant)
    await db_session.flush()

    token = await login(client, member.email)
    response = await client.get(
        f"/organizations/{organization.id}/conversations/"
        f"{conversation.id}/messages/{assistant.id}/pdf",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."


@pytest.mark.asyncio
async def test_user_cannot_export_a_user_message_as_an_answer(client, db_session):
    user = await create_user(db_session, "pdf-user-message@example.com")
    organization = await create_organization(db_session, user)

    conversation = Conversation(
        organization_id=organization.id,
        created_by_user_id=user.id,
        title="User message export",
    )
    db_session.add(conversation)
    await db_session.flush()

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content="This is a question, not an answer.",
    )
    db_session.add(user_message)
    await db_session.flush()

    token = await login(client, user.email)
    response = await client.get(
        f"/organizations/{organization.id}/conversations/"
        f"{conversation.id}/messages/{user_message.id}/pdf",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Assistant message not found."
