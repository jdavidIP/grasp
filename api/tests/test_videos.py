import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.ingestion import videos as ingestion
from app.main import app

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


@pytest.fixture(autouse=True)
def mock_ingestion(monkeypatch):
    monkeypatch.setattr(ingestion, "_extract_metadata", lambda youtube_id: _fake_metadata())
    monkeypatch.setattr(
        ingestion,
        "_fetch_transcript",
        AsyncMock(return_value=([{"start": 0.0, "end": 2.0, "text": "hello"}], "captions")),
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
