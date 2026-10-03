import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ChatSource(BaseModel):
    # None for a "broad" question's sources, which cite whole segments rather than
    # individual chunks — see docs/ARCHITECTURE.md's broad-vs-specific split.
    chunk_id: uuid.UUID | None
    segment_label: str
    start_time: float
    end_time: float
    text: str


class ChatSlip(BaseModel):
    # A known speaker slip the answer relied on: the transcript says `said`, the
    # speaker means `meant` (see #34).
    said: str
    meant: str


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    # Assistant rows only; empty / null for the user's messages.
    sources: list[ChatSource] = []
    grounded: bool | None = None
    slips: list[ChatSlip] = []


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    grounded: bool
    slips: list[ChatSlip]
