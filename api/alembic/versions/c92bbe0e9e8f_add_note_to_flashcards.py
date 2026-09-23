"""add note to flashcards

Revision ID: c92bbe0e9e8f
Revises: b41c7e2d9a05
Create Date: 2026-09-23 00:00:33.699485

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c92bbe0e9e8f"
down_revision: str | Sequence[str] | None = "b41c7e2d9a05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("flashcards", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("flashcards", "note")
