"""add evaluation case metadata snapshot

Revision ID: b2e7a91c4d60
Revises: 618942c83d29
Create Date: 2026-10-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b2e7a91c4d60"
down_revision: Union[str, Sequence[str], None] = "618942c83d29"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Store benchmark metadata with each historical evaluation result."""
    op.add_column(
        "evaluation_results",
        sa.Column(
            "case_metadata_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove the evaluation metadata snapshot."""
    op.drop_column("evaluation_results", "case_metadata_snapshot")
