"""add slips to chat messages

Revision ID: b5d8e2f17a93
Revises: a7c3e9d41f62
Create Date: 2026-10-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5d8e2f17a93"
down_revision: str | Sequence[str] | None = "a7c3e9d41f62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("chat_messages", sa.Column("slips", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("chat_messages", "slips")
