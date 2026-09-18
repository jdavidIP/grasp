"""create quiz tables

Revision ID: b41c7e2d9a05
Revises: 9119cc5ecc2a
Create Date: 2026-09-18 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b41c7e2d9a05"
down_revision: str | Sequence[str] | None = "9119cc5ecc2a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "quizzes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "video_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_quizzes_video_id", "quizzes", ["video_id"])

    op.create_table(
        "quiz_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "quiz_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quizzes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("question_type", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column(
            "segment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transcript_segments.id", ondelete="SET NULL"),
        ),
        sa.Column("source_start_time", sa.Numeric()),
        sa.Column("difficulty", sa.Text()),
    )
    op.create_index("ix_quiz_questions_quiz_id", "quiz_questions", ["quiz_id"])

    op.create_table(
        "quiz_options",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quiz_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("order_index", sa.Integer(), nullable=False),
    )
    op.create_index("ix_quiz_options_question_id", "quiz_options", ["question_id"])

    op.create_table(
        "quiz_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "quiz_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quizzes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Numeric(), nullable=False),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("ix_quiz_attempts_quiz_id", "quiz_attempts", ["quiz_id"])

    op.create_table(
        "quiz_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "attempt_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quiz_attempts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quiz_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "selected_option_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_quiz_answers_attempt_id", "quiz_answers", ["attempt_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("quiz_answers")
    op.drop_table("quiz_attempts")
    op.drop_table("quiz_options")
    op.drop_table("quiz_questions")
    op.drop_table("quizzes")
