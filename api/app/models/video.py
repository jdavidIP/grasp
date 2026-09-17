import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.segment import TranscriptSegment


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    youtube_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    transcript_source: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[list[dict] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    # passive_deletes="all": trust the DB's ON DELETE CASCADE (see the migration)
    # instead of having the ORM null out each segment's video_id before deleting it,
    # which would violate the not-null constraint. Plain passive_deletes=True isn't
    # enough once the collection is already loaded, which lazy="selectin" guarantees.
    segments: Mapped[list[TranscriptSegment]] = relationship(
        order_by=TranscriptSegment.order_index, lazy="selectin", passive_deletes="all"
    )
