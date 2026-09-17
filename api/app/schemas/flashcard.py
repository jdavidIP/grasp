import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FlashcardConfig(BaseModel):
    count: int = Field(ge=5, le=50)
    scope: Literal["whole_video", "topics"]
    segment_ids: list[uuid.UUID] = []
    difficulty: Literal["easy", "medium", "hard", "mixed"] = "mixed"
    style: Literal["definition", "concept", "detail", "mixed"] = "mixed"
    title: str | None = None

    @model_validator(mode="after")
    def _segment_ids_required_for_topics_scope(self) -> "FlashcardConfig":
        if self.scope == "topics" and not self.segment_ids:
            raise ValueError('segment_ids is required when scope is "topics"')
        return self


class FlashcardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    front: str
    back: str
    segment_id: uuid.UUID | None
    source_start_time: float | None
    difficulty: str | None
    order_index: int


class FlashcardDeckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    video_id: uuid.UUID
    title: str
    config: dict
    created_at: datetime
    cards: list[FlashcardOut] = []


class FlashcardDeckListItem(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    title: str
    config: dict
    created_at: datetime
    card_count: int
