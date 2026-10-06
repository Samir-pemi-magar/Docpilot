import uuid

from sqlalchemy import select

from app.models.user import User


async def test_committed_data_is_rolled_back(db_session):
    user = User(
        id=uuid.uuid4(),
        email="rollback-test@example.com",
        password_hash="test-hash",
        full_name="Rollback Test",
    )

    db_session.add(user)

    await db_session.commit()

    result = await db_session.execute(
        select(User).where(User.email == "rollback-test@example.com")
    )

    assert result.scalar_one_or_none() is not None


async def test_previous_test_data_is_gone(db_session):
    result = await db_session.execute(
        select(User).where(User.email == "rollback-test@example.com")
    )

    assert result.scalar_one_or_none() is None
