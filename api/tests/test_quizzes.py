import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import async_session
from app.generation.quiz_grading import InvalidAttempt, grade_attempt
from app.main import app
from app.models.quiz import Quiz
from app.models.quiz_option import QuizOption
from app.models.quiz_question import QuizQuestion
from app.models.video import Video
from app.routers import quizzes as quizzes_router

BASE_URL = "http://test"


async def _create_ready_video() -> uuid.UUID:
    async with async_session() as session:
        video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="t", status="ready")
        session.add(video)
        await session.commit()
        return video.id


def _fake_question(order_index: int, question_type: str, correct: set[int], n_options: int) -> dict:
    # segment_id is a real FK (ON DELETE SET NULL) — use None so the test doesn't need
    # a real transcript_segments row.
    return {
        "question_type": question_type,
        "prompt": f"Q{order_index}",
        "explanation": f"Because {order_index}.",
        "segment_id": None,
        "source_start_time": float(order_index * 10),
        "difficulty": "easy",
        "order_index": order_index,
        "options": [
            {"text": f"opt {i}", "is_correct": i in correct, "order_index": i}
            for i in range(n_options)
        ],
    }


def _fake_questions() -> list[dict]:
    return [
        _fake_question(0, "multiple_choice", {1}, 4),
        _fake_question(1, "multi_select", {0, 2}, 4),
        _fake_question(2, "true_false", {0}, 2),
    ]


@pytest.fixture(autouse=True)
def mock_generate_quiz(monkeypatch):
    monkeypatch.setattr(quizzes_router, "generate_quiz", AsyncMock(return_value=_fake_questions()))


CONFIG = {"count": 5, "scope": "whole_video", "question_types": ["multiple_choice"]}


async def _create_quiz(client: AsyncClient, video_id: uuid.UUID) -> dict:
    response = await client.post(f"/api/videos/{video_id}/quizzes", json=CONFIG)
    assert response.status_code == 201
    return response.json()


def _option_ids(quiz: dict, question_index: int) -> list[str]:
    return [o["id"] for o in quiz["questions"][question_index]["options"]]


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)


async def test_quiz_lifecycle_and_answer_key_is_never_exposed():
    video_id = await _create_ready_video()
    async with _client() as client:
        quiz = await _create_quiz(client, video_id)
        assert quiz["title"] == "Quiz (whole video)"
        assert len(quiz["questions"]) == 3

        fetched = (await client.get(f"/api/quizzes/{quiz['id']}")).json()
        for body in (quiz, fetched):
            text = str(body)
            assert "is_correct" not in text
            assert "explanation" not in text

        listing = (await client.get(f"/api/videos/{video_id}/quizzes")).json()
        assert len(listing) == 1
        assert listing[0]["question_count"] == 3
        assert listing[0]["best_score"] is None

        assert (await client.delete(f"/api/quizzes/{quiz['id']}")).status_code == 204
        assert (await client.get(f"/api/quizzes/{quiz['id']}")).status_code == 404


async def test_attempt_is_graded_from_the_stored_answer_key():
    video_id = await _create_ready_video()
    async with _client() as client:
        quiz = await _create_quiz(client, video_id)
        q0, q1, q2 = (_option_ids(quiz, i) for i in range(3))
        qid = [q["id"] for q in quiz["questions"]]

        response = await client.post(
            f"/api/quizzes/{quiz['id']}/attempts",
            json={
                "answers": [
                    {"question_id": qid[0], "selected_option_ids": [q0[1]]},  # correct
                    {"question_id": qid[1], "selected_option_ids": [q1[0]]},  # only part of set
                    {"question_id": qid[2], "selected_option_ids": [q2[0]]},  # correct
                ]
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["score"] == pytest.approx(2 / 3)
        by_question = {r["question_id"]: r for r in body["results"]}
        assert by_question[qid[0]]["is_correct"] is True
        assert by_question[qid[1]]["is_correct"] is False
        assert by_question[qid[1]]["correct_option_ids"] == [q1[0], q1[2]]
        assert by_question[qid[1]]["selected_option_ids"] == [q1[0]]
        assert by_question[qid[1]]["explanation"] == "Because 1."
        assert by_question[qid[2]]["source_start_time"] == 20.0

        listing = (await client.get(f"/api/videos/{video_id}/quizzes")).json()
        assert listing[0]["best_score"] == pytest.approx(2 / 3)

        history = (await client.get(f"/api/quizzes/{quiz['id']}/attempts")).json()
        assert len(history) == 1
        assert history[0]["correct_count"] == 2
        assert history[0]["question_count"] == 3

        detail = await client.get(f"/api/quizzes/{quiz['id']}/attempts/{history[0]['id']}")
        assert detail.status_code == 200
        assert detail.json() == body  # same per-question results as the submit response

        other_quiz = await _create_quiz(client, video_id)
        wrong_quiz = await client.get(
            f"/api/quizzes/{other_quiz['id']}/attempts/{history[0]['id']}"
        )
        assert wrong_quiz.status_code == 404
        unknown = await client.get(f"/api/quizzes/{quiz['id']}/attempts/{uuid.uuid4()}")
        assert unknown.status_code == 404


async def test_skipped_questions_score_zero_and_multi_select_needs_the_exact_set():
    video_id = await _create_ready_video()
    async with _client() as client:
        quiz = await _create_quiz(client, video_id)
        q1 = _option_ids(quiz, 1)
        response = await client.post(
            f"/api/quizzes/{quiz['id']}/attempts",
            json={
                "answers": [
                    {
                        "question_id": quiz["questions"][1]["id"],
                        "selected_option_ids": [q1[2], q1[0]],  # exact set, any order
                    }
                ]
            },
        )
        body = response.json()
        assert body["score"] == pytest.approx(1 / 3)  # two questions skipped
        assert [r["is_correct"] for r in body["results"]] == [False, True, False]
        assert body["results"][0]["selected_option_ids"] == []


async def test_attempt_rejects_option_ids_that_do_not_belong_to_the_question():
    video_id = await _create_ready_video()
    async with _client() as client:
        quiz = await _create_quiz(client, video_id)
        qid = [q["id"] for q in quiz["questions"]]
        url = f"/api/quizzes/{quiz['id']}/attempts"

        bad_payloads = [
            [{"question_id": qid[0], "selected_option_ids": [str(uuid.uuid4())]}],  # unknown option
            [{"question_id": qid[0], "selected_option_ids": [_option_ids(quiz, 1)[0]]}],  # other Q
            [{"question_id": str(uuid.uuid4()), "selected_option_ids": []}],  # unknown question
            [
                {"question_id": qid[0], "selected_option_ids": []},
                {"question_id": qid[0], "selected_option_ids": []},
            ],  # answered twice
            [{"question_id": qid[0], "selected_option_ids": _option_ids(quiz, 0)[:2]}],  # 2 for MC
            [{"question_id": qid[1], "selected_option_ids": [_option_ids(quiz, 1)[0]] * 2}],
        ]
        for answers in bad_payloads:
            response = await client.post(url, json={"answers": answers})
            assert response.status_code == 422, answers

        history = (await client.get(f"/api/quizzes/{quiz['id']}/attempts")).json()
        assert history == []  # nothing persisted from rejected attempts


async def test_missing_resources_return_404():
    async with _client() as client:
        missing = uuid.uuid4()
        assert (await client.post(f"/api/videos/{missing}/quizzes", json=CONFIG)).status_code == 404
        assert (await client.get(f"/api/videos/{missing}/quizzes")).status_code == 404
        assert (await client.get(f"/api/quizzes/{missing}")).status_code == 404
        assert (await client.delete(f"/api/quizzes/{missing}")).status_code == 404
        assert (
            await client.post(f"/api/quizzes/{missing}/attempts", json={"answers": []})
        ).status_code == 404
        assert (await client.get(f"/api/quizzes/{missing}/attempts")).status_code == 404


async def test_create_quiz_no_generated_questions_returns_422(monkeypatch):
    monkeypatch.setattr(quizzes_router, "generate_quiz", AsyncMock(return_value=[]))
    video_id = await _create_ready_video()
    async with _client() as client:
        response = await client.post(f"/api/videos/{video_id}/quizzes", json=CONFIG)
    assert response.status_code == 422


async def test_create_quiz_validates_config():
    video_id = await _create_ready_video()
    bad_configs = [
        {**CONFIG, "scope": "topics"},  # topics needs segment_ids
        {**CONFIG, "question_types": []},
        {**CONFIG, "question_types": ["short_answer"]},
        {**CONFIG, "count": 2},
        {**CONFIG, "options_per_question": 6},
    ]
    async with _client() as client:
        for config in bad_configs:
            response = await client.post(f"/api/videos/{video_id}/quizzes", json=config)
            assert response.status_code == 422, config


async def test_create_quiz_uses_provided_title():
    video_id = await _create_ready_video()
    async with _client() as client:
        response = await client.post(
            f"/api/videos/{video_id}/quizzes", json={**CONFIG, "title": "Mid-episode check"}
        )
    assert response.json()["title"] == "Mid-episode check"


def _in_memory_quiz() -> tuple[Quiz, QuizQuestion]:
    options = [
        QuizOption(id=uuid.uuid4(), text=f"o{i}", is_correct=i in {0, 1}, order_index=i)
        for i in range(4)
    ]
    question = QuizQuestion(
        id=uuid.uuid4(),
        order_index=0,
        question_type="multi_select",
        prompt="p",
        explanation="e",
        options=options,
    )
    return Quiz(id=uuid.uuid4(), questions=[question]), question


def test_grade_attempt_all_or_nothing_for_multi_select():
    quiz, question = _in_memory_quiz()
    o = [opt.id for opt in question.options]
    assert grade_attempt(quiz, [(question.id, [o[1], o[0]])])[0] == 1.0
    assert grade_attempt(quiz, [(question.id, [o[0]])])[0] == 0.0
    assert grade_attempt(quiz, [(question.id, [o[0], o[1], o[2]])])[0] == 0.0
    assert grade_attempt(quiz, [])[0] == 0.0


def test_grade_attempt_rejects_foreign_option():
    quiz, question = _in_memory_quiz()
    with pytest.raises(InvalidAttempt):
        grade_attempt(quiz, [(question.id, [uuid.uuid4()])])
