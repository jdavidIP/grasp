import uuid

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Flashcard(Base):
    __tablename__ = "flashcards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deck_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("flashcard_decks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)
    segment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transcript_segments.id", ondelete="SET NULL")
    )
    source_start_time: Mapped[float | None] = mapped_column(Numeric)
    difficulty: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(nullable=False)
    # Set when the card's front/back states the corrected fact instead of a speaker
    # slip the transcript contains (wrong name/date/number/etc.) — names the slip, so
    # the divergence from what was actually said is visible instead of silent (#18).
    note: Mapped[str | None] = mapped_column(Text)
