import uuid

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[float] = mapped_column(Numeric, nullable=False)
    end_time: Mapped[float] = mapped_column(Numeric, nullable=False)
