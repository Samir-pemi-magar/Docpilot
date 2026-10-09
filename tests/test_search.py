from __future__ import annotations

import uuid

from app.auth.security import hash_password
from app.embeddings.base import EmbeddingProvider
from app.embeddings.dependencies import get_embedding_provider
from app.embeddings.models import BatchEmbeddingResult, EmbeddingResult
from app.models.chunk import Chunk
from app.models.chunk_embedding import ChunkEmbedding
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User


DIMENSION = 1024
MODEL = "fake-test-model"
PASSWORD = "TestPassword123!"


def make_vector() -> list[float]:
    return [1.0] + [0.0] * (DIMENSION - 1)


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic provider for API tests; does not load an ML model."""

    def embed_query(self, text: str) -> EmbeddingResult:
        return EmbeddingResult(
            vector=make_vector(),
            model=MODEL,
            dimension=DIMENSION,
        )

    def embed_documents(self, texts) -> BatchEmbeddingResult:
        return BatchEmbeddingResult(
            embeddings=[
                EmbeddingResult(
                    vector=make_vector(),
                    model=MODEL,
                    dimension=DIMENSION,
                )
                for _ in texts
            ]
        )


async def create_test_user(db_session, email: str, full_name: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password(PASSWORD),
        full_name=full_name,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def create_test_organization(db_session, owner: User) -> Organization:
    suffix = uuid.uuid4().hex[:12]
    organization = Organization(
        name="Search Test Organization",
        slug=f"search-test-{suffix}",
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


async def add_searchable_chunk(db_session, organization, user):
    text = "DocPilot stores organization-specific information."

    document = Document(
        organization_id=organization.id,
        created_by_user_id=user.id,
        name="Searchable Document",
    )
    db_session.add(document)
    await db_session.flush()

    version = DocumentVersion(
        document_id=document.id,
        uploaded_by_user_id=user.id,
        version_number=1,
        original_filename="information.txt",
        content_type="text/plain",
        size_bytes=len(text.encode()),
        storage_object_key=f"test/{uuid.uuid4()}.txt",
        sha256="a" * 64,
    )
    db_session.add(version)
    await db_session.flush()

    chunk = Chunk(
        document_version_id=version.id,
        chunk_index=0,
        text=text,
        element_type="paragraph",
        source_element_indexes=[],
        metadata_={},
        character_count=len(text),
        token_count=len(text.split()),
    )
    db_session.add(chunk)
    await db_session.flush()

    db_session.add(
        ChunkEmbedding(
            chunk_id=chunk.id,
            model=MODEL,
            dimension=DIMENSION,
            embedding=make_vector(),
        )
    )
    await db_session.flush()

    return chunk


async def login(client, email: str) -> str:
    response = await client.post(
        "/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def test_organization_member_can_search_documents(
    client,
    db_session,
):
    owner = await create_test_user(
        db_session,
        "search-owner@example.com",
        "Search Owner",
    )
    organization = await create_test_organization(db_session, owner)
    chunk = await add_searchable_chunk(db_session, organization, owner)

    app_provider = FakeEmbeddingProvider()
    from app.main import app

    app.dependency_overrides[get_embedding_provider] = lambda: app_provider

    token = await login(client, owner.email)

    response = await client.post(
        f"/organizations/{organization.id}/search",
        json={"query": "organization information", "top_k": 5},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "organization information"
    assert len(data["results"]) == 1
    assert data["results"][0]["chunk_id"] == str(chunk.id)
    assert data["results"][0]["document_version_id"] == str(
        chunk.document_version_id
    )
    assert data["results"][0]["text"] == chunk.text
    assert data["results"][0]["model"] == MODEL
    assert data["results"][0]["distance"] == 0.0


async def test_search_requires_authentication(client, db_session):
    owner = await create_test_user(
        db_session,
        "search-auth-owner@example.com",
        "Search Auth Owner",
    )
    organization = await create_test_organization(db_session, owner)

    response = await client.post(
        f"/organizations/{organization.id}/search",
        json={"query": "organization information"},
    )

    assert response.status_code == 401


async def test_non_member_cannot_search_organization(
    client,
    db_session,
):
    owner = await create_test_user(
        db_session,
        "search-private-owner@example.com",
        "Private Owner",
    )
    outsider = await create_test_user(
        db_session,
        "search-outsider@example.com",
        "Outsider",
    )
    organization = await create_test_organization(db_session, owner)

    from app.main import app

    app.dependency_overrides[get_embedding_provider] = (
        lambda: FakeEmbeddingProvider()
    )

    token = await login(client, outsider.email)

    response = await client.post(
        f"/organizations/{organization.id}/search",
        json={"query": "private information"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


async def test_search_rejects_invalid_top_k(client, db_session):
    owner = await create_test_user(
        db_session,
        "search-validation-owner@example.com",
        "Validation Owner",
    )
    organization = await create_test_organization(db_session, owner)

    from app.main import app

    app.dependency_overrides[get_embedding_provider] = (
        lambda: FakeEmbeddingProvider()
    )

    token = await login(client, owner.email)

    response = await client.post(
        f"/organizations/{organization.id}/search",
        json={"query": "test", "top_k": 101},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
