import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Boolean, CheckConstraint, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("scope IN ('broad', 'specific')", name="ck_chat_messages_scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    cited_chunk_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    # Assistant rows only: which answer path ran, and whether the video covered the
    # question. History rebuilds the sources from these (see docs/DATA_MODEL.md).
    scope: Mapped[str | None] = mapped_column(Text)
    grounded: Mapped[bool | None] = mapped_column(Boolean)
    # Assistant rows only: the known speaker slips the answer relied on, [{said, meant}].
    slips: Mapped[list[dict] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
