"""add password hash to users

Revision ID: 758729bc7295
Revises: 194464cb75ed
Create Date: 2026-10-01 17:05:30.709556

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "758729bc7295"
down_revision: Union[str, Sequence[str], None] = "194464cb75ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing users need a value before the column can become NOT NULL.
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )

    # Temporary development password hash for existing test users.
    # Password: ChangeMe123!
    op.execute(
        sa.text(
            """
            UPDATE users
            SET password_hash = :password_hash
            WHERE password_hash IS NULL
            """
        ).bindparams(
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$ryhsjiVOPIouM8R/msFfHw$mIlTyEY+2nou8sJGVLwP69Xd6+7O4IwfyAwTuWBAOsY"
        )
    )

    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "password_hash")
