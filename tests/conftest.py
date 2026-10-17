from contextlib import asynccontextmanager
import os

os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://docpilot:docpilot_dev@localhost:5433/docpilot_test"
)

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.api.dependencies import (
    get_document_ingestion_task,
    get_storage,
)
from app.auth.security import hash_password
from app.db.session import (
    get_db_session,
    get_evaluation_session_factory,
)
from app.main import app
from app.models.user import User
from app.storage.local import LocalStorage


TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture
async def test_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    async with test_engine.connect() as connection:
        transaction = await connection.begin()

        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
async def test_user(db_session):
    user = User(
        email="test@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Test User",
        is_active=True,
    )

    db_session.add(user)
    await db_session.flush()

    return user


@pytest.fixture
def test_storage(tmp_path):
    return LocalStorage(tmp_path / "storage")


async def _skip_document_ingestion(document_version_id):
    """Keep API tests independent from background processing."""


@pytest.fixture
async def client(db_session, test_storage):
    async def override_get_db_session():
        yield db_session

    @asynccontextmanager
    async def override_evaluation_session_factory():
        # Reuse the test transaction instead of opening the real application DB.
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_evaluation_session_factory] = (
        lambda: override_evaluation_session_factory
    )
    app.dependency_overrides[get_storage] = lambda: test_storage
    app.dependency_overrides[get_document_ingestion_task] = (
        lambda: _skip_document_ingestion
    )

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()
