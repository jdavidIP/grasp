"""add source_end_time to flashcards and quiz_questions

Revision ID: fdf05bcf602f
Revises: b5d8e2f17a93
Create Date: 2026-10-22 01:21:57.312668

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fdf05bcf602f"
down_revision: str | Sequence[str] | None = "b5d8e2f17a93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("flashcards", sa.Column("source_end_time", sa.Numeric(), nullable=True))
    op.add_column("quiz_questions", sa.Column("source_end_time", sa.Numeric(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("quiz_questions", "source_end_time")
    op.drop_column("flashcards", "source_end_time")
