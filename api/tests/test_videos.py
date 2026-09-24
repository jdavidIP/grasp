import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.db import async_session
from app.ingestion import videos as ingestion
from app.main import app
from app.models.chunk import TranscriptChunk

BASE_URL = "http://test"

_real_fetch_transcript = ingestion._fetch_transcript


def _fake_metadata(**overrides):
    return {
        "title": "Test Video",
        "uploader": "Test Channel",
        "duration": 120,
        "thumbnail": "https://example.com/thumb.jpg",
        **overrides,
    }


def _fake_segments():
    return [
        {
            "order_index": 0,
            "label": "Intro",
            "summary": "The intro.",
            "start_time": 0.0,
            "end_time": 2.0,
            "slips": [{"said": "helo", "meant": "hello", "reason": "r"}],
        }
    ]


def _fake_chunks():
    return [
        {
            "text": "hello",
            "start_time": 0.0,
            "end_time": 2.0,
            "token_count": 1,
            "segment_order_index": 0,
            "embedding": [0.1] * 1536,
        }
    ]


@pytest.fixture(autouse=True)
def mock_ingestion(monkeypatch):
    monkeypatch.setattr(ingestion, "_extract_metadata", lambda youtube_id: _fake_metadata())
    monkeypatch.setattr(
        ingestion,
        "_fetch_transcript",
        AsyncMock(return_value=([{"start": 0.0, "end": 2.0, "text": "hello"}], "captions")),
    )
    monkeypatch.setattr(
        ingestion.segmentation, "segment_transcript", AsyncMock(return_value=_fake_segments())
    )
    monkeypatch.setattr(
        ingestion.chunking, "chunk_transcript", AsyncMock(return_value=_fake_chunks())
    )


async def test_video_lifecycle():
    url = f"https://www.youtube.com/watch?v=test-{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_response = await client.post("/api/videos", json={"url": url})
        assert create_response.status_code == 201
        video = create_response.json()
        assert video["status"] == "pending"

        duplicate_response = await client.post("/api/videos", json={"url": url})
        assert duplicate_response.status_code == 409

        list_response = await client.get("/api/videos")
        assert any(v["id"] == video["id"] for v in list_response.json())

        get_response = await client.get(f"/api/videos/{video['id']}")
        assert get_response.status_code == 200
        detail = get_response.json()
        assert detail["status"] == "ready"
        assert detail["transcript_source"] == "captions"
        assert detail["title"] == "Test Video"
        assert len(detail["segments"]) == 1
        assert detail["segments"][0]["label"] == "Intro"

        delete_response = await client.delete(f"/api/videos/{video['id']}")
        assert delete_response.status_code == 204

        list_after_delete = await client.get("/api/videos")
        assert all(v["id"] != video["id"] for v in list_after_delete.json())


async def test_create_video_invalid_url():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post("/api/videos", json={"url": "https://example.com/not-youtube"})
    assert response.status_code == 400


async def test_video_over_duration_fails(monkeypatch):
    monkeypatch.setattr(
        ingestion, "_extract_metadata", lambda youtube_id: _fake_metadata(duration=999_999)
    )
    url = f"https://www.youtube.com/watch?v=test-{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_response = await client.post("/api/videos", json={"url": url})
        video = create_response.json()
        get_response = await client.get(f"/api/videos/{video['id']}")

    detail = get_response.json()
    assert detail["status"] == "failed"
    assert "limit" in detail["error_message"].lower()


async def test_video_unknown_duration_fails(monkeypatch):
    monkeypatch.setattr(
        ingestion, "_extract_metadata", lambda youtube_id: _fake_metadata(duration=None)
    )
    url = f"https://www.youtube.com/watch?v=test-{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_response = await client.post("/api/videos", json={"url": url})
        video = create_response.json()
        get_response = await client.get(f"/api/videos/{video['id']}")

    detail = get_response.json()
    assert detail["status"] == "failed"
    assert "duration" in detail["error_message"].lower()


async def test_empty_captions_falls_back_to_whisper(monkeypatch):
    # The autouse mock_ingestion fixture replaces _fetch_transcript itself, so
    # restore the real implementation to exercise its actual fallback logic.
    monkeypatch.setattr(ingestion, "_fetch_transcript", _real_fetch_transcript)
    monkeypatch.setattr(ingestion, "_fetch_captions", lambda youtube_id: [])
    monkeypatch.setattr(ingestion, "_download_audio", lambda youtube_id, tmp_dir: Path("fake.m4a"))
    monkeypatch.setattr(
        ingestion.llm,
        "transcribe_audio",
        AsyncMock(return_value=[{"start": 0.0, "end": 1.0, "text": "hi"}]),
    )

    cues, source = await ingestion._fetch_transcript("abc123")

    assert source == "whisper"
    assert cues == [{"start": 0.0, "end": 1.0, "text": "hi"}]


async def test_reprocess_regenerates_segments():
    url = f"https://www.youtube.com/watch?v=test-{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_response = await client.post("/api/videos", json={"url": url})
        video = create_response.json()

        reprocess_response = await client.post(f"/api/videos/{video['id']}/reprocess")
        assert reprocess_response.status_code == 202

        get_response = await client.get(f"/api/videos/{video['id']}")

    detail = get_response.json()
    assert detail["status"] == "ready"
    assert len(detail["segments"]) == 1


async def test_reprocess_missing_video_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(f"/api/videos/{uuid.uuid4()}/reprocess")
    assert response.status_code == 404


async def test_video_llm_error_during_ingestion_stores_its_message(monkeypatch):
    monkeypatch.setattr(
        ingestion.segmentation,
        "segment_transcript",
        AsyncMock(side_effect=ingestion.llm.LLMError("OpenAI rejected the API key.")),
    )
    url = f"https://www.youtube.com/watch?v=test-{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_response = await client.post("/api/videos", json={"url": url})
        video = create_response.json()
        get_response = await client.get(f"/api/videos/{video['id']}")

    detail = get_response.json()
    assert detail["status"] == "failed"
    assert detail["error_message"] == "OpenAI rejected the API key."


async def test_reprocess_llm_error_stores_its_message(monkeypatch):
    url = f"https://www.youtube.com/watch?v=test-{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_response = await client.post("/api/videos", json={"url": url})
        video = create_response.json()

        monkeypatch.setattr(
            ingestion.segmentation,
            "segment_transcript",
            AsyncMock(side_effect=ingestion.llm.LLMError("Hit an OpenAI rate limit or quota.")),
        )
        reprocess_response = await client.post(f"/api/videos/{video['id']}/reprocess")
        assert reprocess_response.status_code == 202

        get_response = await client.get(f"/api/videos/{video['id']}")

    detail = get_response.json()
    assert detail["status"] == "failed"
    assert detail["error_message"] == "Hit an OpenAI rate limit or quota."
    # The failed reprocess must not have wiped what the first ingestion stored.
    assert [s["label"] for s in detail["segments"]] == ["Intro"]
    assert await _chunk_count(video["id"]) == 1


async def test_successful_reprocess_clears_the_previous_error(monkeypatch):
    url = f"https://www.youtube.com/watch?v=test-{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        video = (await client.post("/api/videos", json={"url": url})).json()

        with monkeypatch.context() as m:
            m.setattr(
                ingestion.segmentation,
                "segment_transcript",
                AsyncMock(side_effect=ingestion.llm.LLMError("Hit an OpenAI rate limit.")),
            )
            await client.post(f"/api/videos/{video['id']}/reprocess")
        await client.post(f"/api/videos/{video['id']}/reprocess")
        detail = (await client.get(f"/api/videos/{video['id']}")).json()

    assert detail["status"] == "ready"
    assert detail["error_message"] is None


async def test_reprocess_failing_mid_write_rolls_back(monkeypatch):
    url = f"https://www.youtube.com/watch?v=test-{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_response = await client.post("/api/videos", json={"url": url})
        video = create_response.json()

        # A chunk pointing at a segment that doesn't exist fails after the old
        # segments were deleted and the new ones flushed.
        bad_chunk = {**_fake_chunks()[0], "segment_order_index": 99}
        monkeypatch.setattr(
            ingestion.chunking, "chunk_transcript", AsyncMock(return_value=[bad_chunk])
        )
        await client.post(f"/api/videos/{video['id']}/reprocess")
        get_response = await client.get(f"/api/videos/{video['id']}")

    detail = get_response.json()
    assert detail["status"] == "failed"
    assert detail["error_message"] == "Reprocessing failed unexpectedly."
    assert [s["label"] for s in detail["segments"]] == ["Intro"]
    assert await _chunk_count(video["id"]) == 1


async def _chunk_count(video_id: str) -> int:
    async with async_session() as session:
        return await session.scalar(
            select(func.count())
            .select_from(TranscriptChunk)
            .where(TranscriptChunk.video_id == uuid.UUID(video_id))
        )


async def test_video_no_transcript_fails(monkeypatch):
    monkeypatch.setattr(ingestion, "_fetch_transcript", AsyncMock(return_value=([], "captions")))
    url = f"https://www.youtube.com/watch?v=test-{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_response = await client.post("/api/videos", json={"url": url})
        video = create_response.json()
        get_response = await client.get(f"/api/videos/{video['id']}")

    detail = get_response.json()
    assert detail["status"] == "failed"
    assert detail["error_message"]
