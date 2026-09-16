"""add transcript to videos

Revision ID: f6145304bb69
Revises: 2469263766ae
Create Date: 2026-09-16 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6145304bb69"
down_revision: str | Sequence[str] | None = "2469263766ae"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("videos", sa.Column("transcript", postgresql.JSONB(astext_type=sa.Text())))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("videos", "transcript")
