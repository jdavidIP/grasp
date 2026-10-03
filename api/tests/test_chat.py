import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db import async_session
from app.generation.llm import LLMError
from app.main import app
from app.models.chat_message import ChatMessage
from app.models.chunk import TranscriptChunk
from app.models.segment import TranscriptSegment
from app.models.video import Video
from app.routers import chat as chat_router

BASE_URL = "http://test"


async def _create_ready_video() -> uuid.UUID:
    async with async_session() as session:
        video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="t", status="ready")
        session.add(video)
        await session.commit()
        return video.id


async def _create_video_with_chunks() -> tuple[uuid.UUID, list[uuid.UUID]]:
    """A ready video with two segments and one chunk in each; returns the chunk ids."""
    async with async_session() as session:
        video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="t", status="ready")
        session.add(video)
        await session.flush()
        chunk_ids = []
        for i, (label, start, end) in enumerate([("Intro", 8.0, 148.0), ("Loops", 148.0, 300.0)]):
            segment = TranscriptSegment(
                video_id=video.id,
                order_index=i,
                label=label,
                summary=f"{label} summary.",
                start_time=start,
                end_time=end,
            )
            session.add(segment)
            await session.flush()
            chunk = TranscriptChunk(
                video_id=video.id,
                segment_id=segment.id,
                text=f"{label} excerpt",
                start_time=start,
                end_time=start + 20,
            )
            session.add(chunk)
            await session.flush()
            chunk_ids.append(chunk.id)
        await session.commit()
        return video.id, chunk_ids


def _fake_answer(sources=None, grounded=True, path="specific"):
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
        "grounded": grounded,
        "path": path,
    }


def _chunk_source(chunk_id: uuid.UUID) -> dict:
    # Only chunk_id matters to what's saved; history rebuilds the rest from the row.
    return {
        "chunk_id": chunk_id,
        "segment_label": "x",
        "start_time": 0.0,
        "end_time": 0.0,
        "text": "x",
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


async def test_chat_llm_error_returns_502_with_its_message(monkeypatch):
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

    assert response.status_code == 502
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
                ],
                path="broad",
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
        assert assistant_message.scope == "broad"
        assert assistant_message.grounded is True


async def test_history_rebuilds_specific_sources_in_saved_order(monkeypatch):
    video_id, (intro_chunk, loops_chunk) = await _create_video_with_chunks()
    monkeypatch.setattr(
        chat_router,
        "answer_question",
        AsyncMock(
            return_value=_fake_answer([_chunk_source(loops_chunk), _chunk_source(intro_chunk)])
        ),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        await client.post(f"/api/videos/{video_id}/chat", json={"message": "q"})
        history = (await client.get(f"/api/videos/{video_id}/chat")).json()

    user, assistant = history
    assert user["sources"] == [] and user["grounded"] is None
    assert assistant["grounded"] is True
    assert [(s["segment_label"], s["text"], s["start_time"]) for s in assistant["sources"]] == [
        ("Loops", "Loops excerpt", 148.0),
        ("Intro", "Intro excerpt", 8.0),
    ]
    assert assistant["sources"][0]["chunk_id"] == str(loops_chunk)


async def test_history_lists_every_segment_for_a_broad_answer(monkeypatch):
    video_id, _ = await _create_video_with_chunks()
    monkeypatch.setattr(
        chat_router, "answer_question", AsyncMock(return_value=_fake_answer([], path="broad"))
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        await client.post(f"/api/videos/{video_id}/chat", json={"message": "summarize"})
        assistant = (await client.get(f"/api/videos/{video_id}/chat")).json()[1]

    assert [
        (s["chunk_id"], s["segment_label"], s["start_time"], s["end_time"], s["text"])
        for s in assistant["sources"]
    ] == [
        (None, "Intro", 8.0, 148.0, "Intro summary."),
        (None, "Loops", 148.0, 300.0, "Loops summary."),
    ]


async def test_history_keeps_an_ungrounded_answer_ungrounded(monkeypatch):
    video_id = await _create_ready_video()
    monkeypatch.setattr(
        chat_router, "answer_question", AsyncMock(return_value=_fake_answer([], grounded=False))
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        await client.post(f"/api/videos/{video_id}/chat", json={"message": "off topic"})
        assistant = (await client.get(f"/api/videos/{video_id}/chat")).json()[1]

    assert assistant["grounded"] is False
    assert assistant["sources"] == []


async def test_history_skips_a_cited_chunk_that_no_longer_exists(monkeypatch):
    # An answer computed mid-reprocess can commit after the chunks it cites were replaced.
    video_id, (intro_chunk, _) = await _create_video_with_chunks()
    monkeypatch.setattr(
        chat_router,
        "answer_question",
        AsyncMock(
            return_value=_fake_answer([_chunk_source(uuid.uuid4()), _chunk_source(intro_chunk)])
        ),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        await client.post(f"/api/videos/{video_id}/chat", json={"message": "q"})
        response = await client.get(f"/api/videos/{video_id}/chat")

    assert response.status_code == 200
    assert [s["segment_label"] for s in response.json()[1]["sources"]] == ["Intro"]
