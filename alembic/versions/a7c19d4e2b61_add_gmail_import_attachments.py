"""Add Gmail attachment import tracking.

Revision ID: a7c19d4e2b61
Revises: 13e2a56a8a32
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c19d4e2b61"
down_revision: Union[str, Sequence[str], None] = "13e2a56a8a32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gmail_import_attachments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("gmail_import_id", sa.UUID(), nullable=False),
        sa.Column("gmail_attachment_id", sa.String(512), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(30),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["gmail_import_id"],
            ["gmail_imports.id"],
            name="fk_gmail_import_attachments_gmail_import_id_gmail_imports",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_gmail_import_attachments_document_id_documents",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "gmail_import_id",
            "gmail_attachment_id",
            name="uq_gmail_import_attachments_import_attachment",
        ),
    )
    op.create_index(
        "ix_gmail_import_attachments_gmail_import_id",
        "gmail_import_attachments",
        ["gmail_import_id"],
    )
    op.create_index(
        "ix_gmail_import_attachments_document_id",
        "gmail_import_attachments",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_gmail_import_attachments_document_id",
        table_name="gmail_import_attachments",
    )
    op.drop_index(
        "ix_gmail_import_attachments_gmail_import_id",
        table_name="gmail_import_attachments",
    )
    op.drop_table("gmail_import_attachments")
