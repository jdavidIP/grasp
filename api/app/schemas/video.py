import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VideoCreate(BaseModel):
    url: str


class VideoListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    youtube_id: str
    title: str
    channel: str | None
    duration_seconds: int | None
    thumbnail_url: str | None
    status: str
    created_at: datetime


class VideoDetail(VideoListItem):
    error_message: str | None
    transcript_source: str | None
