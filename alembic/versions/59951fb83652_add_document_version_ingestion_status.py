"""add document version ingestion status

Revision ID: 59951fb83652
Revises: a690a96a1c58
Create Date: 2026-10-09 02:39:14.524804
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "59951fb83652"
down_revision: Union[str, Sequence[str], None] = "a690a96a1c58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_versions",
        sa.Column(
            "ingestion_status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_document_versions_ingestion_status",
        "document_versions",
        "ingestion_status IN ('pending', 'processing', 'completed', 'failed')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_document_versions_ingestion_status",
        "document_versions",
        type_="check",
    )
    op.drop_column("document_versions", "ingestion_status")
