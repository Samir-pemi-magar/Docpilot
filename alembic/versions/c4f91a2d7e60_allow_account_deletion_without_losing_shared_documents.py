"""Allow account deletion without losing shared documents.

Revision ID: c4f91a2d7e60
Revises: b2e7a91c4d60
"""
from alembic import op
import sqlalchemy as sa

revision = "c4f91a2d7e60"
down_revision = "b2e7a91c4d60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "documents",
        "created_by_user_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.alter_column(
        "document_versions",
        "uploaded_by_user_id",
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    # Downgrade will fail if any deleted-user attribution is still NULL.
    op.alter_column(
        "document_versions",
        "uploaded_by_user_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.alter_column(
        "documents",
        "created_by_user_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
