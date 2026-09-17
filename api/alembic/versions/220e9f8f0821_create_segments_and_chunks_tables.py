"""create transcript_segments and transcript_chunks tables

Revision ID: 220e9f8f0821
Revises: f6145304bb69
Create Date: 2026-09-16 00:00:00.000000

"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "220e9f8f0821"
down_revision: str | Sequence[str] | None = "f6145304bb69"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "transcript_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "video_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("start_time", sa.Numeric(), nullable=False),
        sa.Column("end_time", sa.Numeric(), nullable=False),
    )
    op.create_index(
        "ix_transcript_segments_video_id_order_index",
        "transcript_segments",
        ["video_id", "order_index"],
    )

    op.create_table(
        "transcript_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "video_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "segment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transcript_segments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_time", sa.Numeric(), nullable=False),
        sa.Column("end_time", sa.Numeric(), nullable=False),
        sa.Column("token_count", sa.Integer()),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(1536)),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', text)", persisted=True),
        ),
    )
    op.create_index("ix_transcript_chunks_video_id", "transcript_chunks", ["video_id"])
    op.create_index("ix_transcript_chunks_segment_id", "transcript_chunks", ["segment_id"])
    op.execute(
        "CREATE INDEX ix_transcript_chunks_embedding_hnsw ON transcript_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute("CREATE INDEX ix_transcript_chunks_tsv ON transcript_chunks USING gin (tsv)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("transcript_chunks")
    op.drop_table("transcript_segments")
