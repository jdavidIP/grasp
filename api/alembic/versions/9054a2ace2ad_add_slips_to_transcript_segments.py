"""add slips to transcript segments

Revision ID: 9054a2ace2ad
Revises: c92bbe0e9e8f
Create Date: 2026-09-24 04:14:52.654583

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9054a2ace2ad"
down_revision: str | Sequence[str] | None = "c92bbe0e9e8f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "transcript_segments",
        sa.Column(
            "slips",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("transcript_segments", "slips")
