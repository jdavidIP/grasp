import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db import async_session
from app.generation.llm import LLMError
from app.main import app
from app.models.chat_message import ChatMessage
from app.models.video import Video
from app.routers import chat as chat_router

BASE_URL = "http://test"


async def _create_ready_video() -> uuid.UUID:
    async with async_session() as session:
        video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="t", status="ready")
        session.add(video)
        await session.commit()
        return video.id


def _fake_answer(sources=None):
    return {
        "answer": "The answer.",
        "sources": sources
        if sources is not None
        else [
            {
                "chunk_id": uuid.uuid4(),
                "segment_label": "Intro",
                "start_time": 0.0,
                "end_time": 5.0,
                "text": "excerpt",
            }
        ],
        "grounded": True,
    }


@pytest.fixture(autouse=True)
def mock_answer_question(monkeypatch):
    monkeypatch.setattr(chat_router, "answer_question", AsyncMock(return_value=_fake_answer()))


async def test_chat_lifecycle():
    video_id = await _create_ready_video()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        post_response = await client.post(
            f"/api/videos/{video_id}/chat", json={"message": "What did they say?"}
        )
        assert post_response.status_code == 200
        body = post_response.json()
        assert body["answer"] == "The answer."
        assert body["grounded"] is True
        assert body["sources"][0]["segment_label"] == "Intro"

        history_response = await client.get(f"/api/videos/{video_id}/chat")
        history = history_response.json()
        assert [m["role"] for m in history] == ["user", "assistant"]
        assert history[0]["content"] == "What did they say?"
        assert history[1]["content"] == "The answer."

        delete_response = await client.delete(f"/api/videos/{video_id}/chat")
        assert delete_response.status_code == 204

        empty_history = await client.get(f"/api/videos/{video_id}/chat")
        assert empty_history.json() == []


async def test_chat_missing_video_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(f"/api/videos/{uuid.uuid4()}/chat", json={"message": "hi"})
    assert response.status_code == 404


async def test_get_chat_history_missing_video_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.get(f"/api/videos/{uuid.uuid4()}/chat")
    assert response.status_code == 404


async def test_clear_chat_history_missing_video_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.delete(f"/api/videos/{uuid.uuid4()}/chat")
    assert response.status_code == 404


async def test_chat_llm_error_returns_503_with_its_message(monkeypatch):
    monkeypatch.setattr(
        chat_router,
        "answer_question",
        AsyncMock(
            side_effect=LLMError("Hit an OpenAI rate limit or quota. Try again in a moment.")
        ),
    )
    video_id = await _create_ready_video()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(f"/api/videos/{video_id}/chat", json={"message": "hi"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Hit an OpenAI rate limit or quota. Try again in a moment."
    }


async def test_chat_passes_recent_history_to_generation(monkeypatch):
    mock_answer = AsyncMock(return_value=_fake_answer())
    monkeypatch.setattr(chat_router, "answer_question", mock_answer)

    video_id = await _create_ready_video()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        await client.post(f"/api/videos/{video_id}/chat", json={"message": "first question"})
        await client.post(f"/api/videos/{video_id}/chat", json={"message": "second question"})

    second_call_history = mock_answer.await_args_list[1].args[3]
    assert second_call_history == [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "The answer."},
    ]


async def test_chat_broad_sources_store_null_cited_chunk_ids(monkeypatch):
    monkeypatch.setattr(
        chat_router,
        "answer_question",
        AsyncMock(
            return_value=_fake_answer(
                sources=[
                    {
                        "chunk_id": None,
                        "segment_label": "Intro",
                        "start_time": 0.0,
                        "end_time": 5.0,
                        "text": "summary",
                    }
                ]
            )
        ),
    )

    video_id = await _create_ready_video()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        await client.post(f"/api/videos/{video_id}/chat", json={"message": "summarize"})

    async with async_session() as session:
        result = await session.execute(
            select(ChatMessage).where(
                ChatMessage.video_id == video_id, ChatMessage.role == "assistant"
            )
        )
        assistant_message = result.scalar_one()
        assert assistant_message.cited_chunk_ids is None
