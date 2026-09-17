import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    created_at: datetime


class ChatRequest(BaseModel):
    message: str


class ChatSource(BaseModel):
    chunk_id: uuid.UUID
    segment_label: str
    start_time: float
    end_time: float
    text: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    grounded: bool
