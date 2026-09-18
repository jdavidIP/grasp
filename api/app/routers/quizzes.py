import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.generation.quiz_grading import InvalidAttempt, grade_attempt
from app.generation.quizzes import generate_quiz
from app.models.quiz import Quiz
from app.models.quiz_answer import QuizAnswer
from app.models.quiz_attempt import QuizAttempt
from app.models.quiz_option import QuizOption
from app.models.quiz_question import QuizQuestion
from app.models.video import Video
from app.schemas.quiz import (
    AttemptIn,
    AttemptListItem,
    AttemptResult,
    QuizConfig,
    QuizListItem,
    QuizOut,
)

router = APIRouter()


def _default_title(config: QuizConfig) -> str:
    scope_label = "whole video" if config.scope == "whole_video" else "selected topics"
    return f"Quiz ({scope_label})"


async def _get_quiz_or_404(db: AsyncSession, quiz_id: uuid.UUID) -> Quiz:
    quiz = await db.get(Quiz, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    return quiz


@router.post("/videos/{video_id}/quizzes", response_model=QuizOut, status_code=201)
async def create_quiz(
    video_id: uuid.UUID, payload: QuizConfig, db: AsyncSession = Depends(get_db)
) -> Quiz:
    video = await db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    questions = await generate_quiz(
        db,
        video_id,
        count=payload.count,
        scope=payload.scope,
        segment_ids=payload.segment_ids,
        question_types=payload.question_types,
        options_per_question=payload.options_per_question,
        difficulty=payload.difficulty,
    )
    if not questions:
        raise HTTPException(
            status_code=422, detail="Could not generate any questions for this configuration."
        )

    quiz = Quiz(
        video_id=video_id,
        title=payload.title or _default_title(payload),
        config=payload.model_dump(mode="json"),
    )
    quiz.questions = [
        QuizQuestion(
            **{k: v for k, v in question.items() if k != "options"},
            options=[QuizOption(**option) for option in question["options"]],
        )
        for question in questions
    ]
    db.add(quiz)
    await db.commit()
    await db.refresh(quiz)
    return quiz


@router.get("/videos/{video_id}/quizzes", response_model=list[QuizListItem])
async def list_quizzes(
    video_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[QuizListItem]:
    if await db.get(Video, video_id) is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    result = await db.execute(
        select(Quiz).where(Quiz.video_id == video_id).order_by(Quiz.created_at.desc())
    )
    quizzes = result.scalars().all()

    best_result = await db.execute(
        select(QuizAttempt.quiz_id, func.max(QuizAttempt.score))
        .where(QuizAttempt.quiz_id.in_([q.id for q in quizzes]))
        .group_by(QuizAttempt.quiz_id)
    )
    best_scores = {quiz_id: float(score) for quiz_id, score in best_result.all()}

    return [
        QuizListItem(
            id=quiz.id,
            video_id=quiz.video_id,
            title=quiz.title,
            config=quiz.config,
            created_at=quiz.created_at,
            question_count=len(quiz.questions),
            best_score=best_scores.get(quiz.id),
        )
        for quiz in quizzes
    ]


@router.get("/quizzes/{quiz_id}", response_model=QuizOut)
async def get_quiz(quiz_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Quiz:
    return await _get_quiz_or_404(db, quiz_id)


@router.delete("/quizzes/{quiz_id}", status_code=204)
async def delete_quiz(quiz_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    quiz = await _get_quiz_or_404(db, quiz_id)
    await db.delete(quiz)
    await db.commit()


@router.post("/quizzes/{quiz_id}/attempts", response_model=AttemptResult, status_code=201)
async def submit_attempt(
    quiz_id: uuid.UUID, payload: AttemptIn, db: AsyncSession = Depends(get_db)
) -> AttemptResult:
    quiz = await _get_quiz_or_404(db, quiz_id)
    try:
        score, results = grade_attempt(
            quiz, [(a.question_id, a.selected_option_ids) for a in payload.answers]
        )
    except InvalidAttempt as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    attempt = QuizAttempt(quiz_id=quiz_id, score=score, completed_at=datetime.now(UTC))
    attempt.answers = [
        QuizAnswer(
            question_id=r["question_id"],
            selected_option_ids=r["selected_option_ids"],
            is_correct=r["is_correct"],
        )
        for r in results
    ]
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return AttemptResult(attempt_id=attempt.id, score=score, results=results)


@router.get("/quizzes/{quiz_id}/attempts", response_model=list[AttemptListItem])
async def list_attempts(
    quiz_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[AttemptListItem]:
    quiz = await _get_quiz_or_404(db, quiz_id)
    result = await db.execute(
        select(QuizAttempt)
        .where(QuizAttempt.quiz_id == quiz_id)
        .order_by(QuizAttempt.started_at.desc())
    )
    return [
        AttemptListItem(
            id=attempt.id,
            score=float(attempt.score),
            correct_count=sum(a.is_correct for a in attempt.answers),
            question_count=len(quiz.questions),
            started_at=attempt.started_at,
            completed_at=attempt.completed_at,
        )
        for attempt in result.scalars()
    ]


@router.get("/quizzes/{quiz_id}/attempts/{attempt_id}", response_model=AttemptResult)
async def get_attempt(
    quiz_id: uuid.UUID, attempt_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> AttemptResult:
    quiz = await _get_quiz_or_404(db, quiz_id)
    attempt = await db.get(QuizAttempt, attempt_id)
    if attempt is None or attempt.quiz_id != quiz_id:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    # The answer key never changes after generation, so re-grading the stored
    # selections reproduces exactly what the submit response showed.
    _, results = grade_attempt(
        quiz, [(a.question_id, a.selected_option_ids) for a in attempt.answers]
    )
    return AttemptResult(attempt_id=attempt.id, score=float(attempt.score), results=results)
