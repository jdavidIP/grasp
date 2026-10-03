"""add scope and grounded to chat messages

Revision ID: a7c3e9d41f62
Revises: 9054a2ace2ad
Create Date: 2026-10-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c3e9d41f62"
down_revision: str | Sequence[str] | None = "9054a2ace2ad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing rows have no scope, so their sources can't be rebuilt. Cleared once on
    # purpose (single local user) rather than shown half-filled.
    op.execute("DELETE FROM chat_messages")
    op.add_column("chat_messages", sa.Column("scope", sa.Text(), nullable=True))
    op.add_column("chat_messages", sa.Column("grounded", sa.Boolean(), nullable=True))
    op.create_check_constraint(
        "ck_chat_messages_scope", "chat_messages", "scope IN ('broad', 'specific')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_chat_messages_scope", "chat_messages", type_="check")
    op.drop_column("chat_messages", "grounded")
    op.drop_column("chat_messages", "scope")
