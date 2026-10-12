"""add chunk text search index

Revision ID: 618942c83d29
Revises: a3ed5f65c7ce
Create Date: 2026-10-12 01:49:36.087937
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "618942c83d29"
down_revision: Union[str, Sequence[str], None] = "a3ed5f65c7ce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create an index for PostgreSQL full-text search over chunk text."""
    op.create_index(
        "ix_chunks_text_search",
        "chunks",
        [sa.text("to_tsvector('simple'::regconfig, text)")],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Remove the full-text search index."""
    op.drop_index(
        "ix_chunks_text_search",
        table_name="chunks",
    )
