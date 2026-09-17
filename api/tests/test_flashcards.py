import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import async_session
from app.main import app
from app.models.video import Video
from app.routers import flashcards as flashcards_router

BASE_URL = "http://test"


async def _create_ready_video() -> uuid.UUID:
    async with async_session() as session:
        video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="t", status="ready")
        session.add(video)
        await session.commit()
        return video.id


def _fake_cards(n: int = 2) -> list[dict]:
    # segment_id is a real FK (ON DELETE SET NULL) — use None rather than a
    # random uuid so the test doesn't need a real transcript_segments row.
    return [
        {
            "front": f"Q{i}",
            "back": f"A{i}",
            "segment_id": None,
            "source_start_time": float(i),
            "difficulty": "easy",
            "order_index": i,
        }
        for i in range(n)
    ]


@pytest.fixture(autouse=True)
def mock_generate_flashcards(monkeypatch):
    monkeypatch.setattr(
        flashcards_router, "generate_flashcards", AsyncMock(return_value=_fake_cards())
    )


async def test_flashcard_deck_lifecycle():
    video_id = await _create_ready_video()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_response = await client.post(
            f"/api/videos/{video_id}/flashcard-decks",
            json={"count": 10, "scope": "whole_video"},
        )
        assert create_response.status_code == 201
        deck = create_response.json()
        assert len(deck["cards"]) == 2
        assert deck["title"] == "Flashcards (whole video)"
        deck_id = deck["id"]

        list_response = await client.get(f"/api/videos/{video_id}/flashcard-decks")
        assert list_response.status_code == 200
        decks = list_response.json()
        assert len(decks) == 1
        assert decks[0]["card_count"] == 2

        get_response = await client.get(f"/api/flashcard-decks/{deck_id}")
        assert get_response.status_code == 200
        assert len(get_response.json()["cards"]) == 2

        delete_response = await client.delete(f"/api/flashcard-decks/{deck_id}")
        assert delete_response.status_code == 204

        missing_response = await client.get(f"/api/flashcard-decks/{deck_id}")
        assert missing_response.status_code == 404


async def test_create_deck_missing_video_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            f"/api/videos/{uuid.uuid4()}/flashcard-decks",
            json={"count": 10, "scope": "whole_video"},
        )
    assert response.status_code == 404


async def test_list_decks_missing_video_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.get(f"/api/videos/{uuid.uuid4()}/flashcard-decks")
    assert response.status_code == 404


async def test_get_deck_missing_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.get(f"/api/flashcard-decks/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_delete_deck_missing_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.delete(f"/api/flashcard-decks/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_create_deck_no_generated_cards_returns_422(monkeypatch):
    monkeypatch.setattr(flashcards_router, "generate_flashcards", AsyncMock(return_value=[]))
    video_id = await _create_ready_video()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            f"/api/videos/{video_id}/flashcard-decks",
            json={"count": 10, "scope": "whole_video"},
        )
    assert response.status_code == 422


async def test_create_deck_topics_scope_requires_segment_ids():
    video_id = await _create_ready_video()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            f"/api/videos/{video_id}/flashcard-decks",
            json={"count": 10, "scope": "topics"},
        )
    assert response.status_code == 422


async def test_create_deck_uses_provided_title():
    video_id = await _create_ready_video()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            f"/api/videos/{video_id}/flashcard-decks",
            json={"count": 10, "scope": "whole_video", "title": "My Deck"},
        )
    assert response.json()["title"] == "My Deck"
