import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

QuestionType = Literal["multiple_choice", "multi_select", "true_false"]


class QuizConfig(BaseModel):
    count: int = Field(ge=3, le=30)
    scope: Literal["whole_video", "topics"]
    segment_ids: list[uuid.UUID] = []
    question_types: list[QuestionType] = Field(min_length=1)
    options_per_question: int = Field(default=4, ge=3, le=5)
    difficulty: Literal["easy", "medium", "hard", "mixed"] = "mixed"
    title: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "QuizConfig":
        if self.scope == "topics" and not self.segment_ids:
            raise ValueError('segment_ids is required when scope is "topics"')
        self.question_types = list(dict.fromkeys(self.question_types))
        return self


# Question and option output deliberately omit `is_correct` and `explanation`: they are
# the answer key, revealed only in the attempt-submit response.
class QuizOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    order_index: int


class QuizQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_index: int
    question_type: QuestionType
    prompt: str
    difficulty: str | None
    options: list[QuizOptionOut]


class QuizOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    video_id: uuid.UUID
    title: str
    config: dict
    created_at: datetime
    questions: list[QuizQuestionOut] = []


class QuizListItem(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    title: str
    config: dict
    created_at: datetime
    question_count: int
    best_score: float | None


class AnswerIn(BaseModel):
    question_id: uuid.UUID
    selected_option_ids: list[uuid.UUID] = []


class AttemptIn(BaseModel):
    answers: list[AnswerIn]


class QuestionResult(BaseModel):
    question_id: uuid.UUID
    is_correct: bool
    selected_option_ids: list[uuid.UUID]
    correct_option_ids: list[uuid.UUID]
    explanation: str
    segment_id: uuid.UUID | None
    source_start_time: float | None


class AttemptResult(BaseModel):
    attempt_id: uuid.UUID
    score: float
    results: list[QuestionResult]


class AttemptListItem(BaseModel):
    id: uuid.UUID
    score: float
    correct_count: int
    question_count: int
    started_at: datetime
    completed_at: datetime | None
