import uuid
from unittest.mock import AsyncMock

from app.db import async_session
from app.generation import flashcards
from app.models.chunk import TranscriptChunk
from app.models.segment import TranscriptSegment
from app.models.video import Video


def _embedding(*nonzero_indices: int) -> list[float]:
    vec = [0.0] * 1536
    for i in nonzero_indices:
        vec[i] = 1.0
    return vec


async def test_generate_candidates_filters_structurally_invalid_cards(monkeypatch):
    monkeypatch.setattr(
        flashcards.llm,
        "generate_json",
        AsyncMock(
            return_value={
                "cards": [
                    {"front": "Q1", "back": "A1", "topic_index": 0, "difficulty": "easy"},
                    {"front": "", "back": "A2", "topic_index": 0, "difficulty": "easy"},
                    {"front": "Q3", "back": "A3", "topic_index": 99, "difficulty": "easy"},
                    {"front": "Q4", "back": "A4", "topic_index": 0, "difficulty": "impossible"},
                    "not a dict",
                ]
            }
        ),
    )

    cards = await flashcards._generate_candidates(2, "easy", "mixed", [("Topic", "text")])

    assert [c["front"] for c in cards] == ["Q1", "Q4"]
    assert cards[1]["difficulty"] == "easy"  # falls back to the requested difficulty


async def test_generate_candidates_malformed_response_returns_empty(monkeypatch):
    monkeypatch.setattr(flashcards.llm, "generate_json", AsyncMock(return_value={}))

    assert await flashcards._generate_candidates(2, "easy", "mixed", [("Topic", "text")]) == []


async def test_filter_grounded_keeps_only_listed_indices(monkeypatch):
    monkeypatch.setattr(
        flashcards.llm, "generate_json", AsyncMock(return_value={"grounded_card_indices": [1]})
    )
    cards = [
        {"front": "Q1", "back": "A1", "topic_index": 0, "difficulty": "easy"},
        {"front": "Q2", "back": "A2", "topic_index": 0, "difficulty": "easy"},
    ]

    grounded = await flashcards._filter_grounded(["text"], cards)

    assert grounded == [cards[1]]


async def test_filter_grounded_malformed_response_drops_all(monkeypatch):
    monkeypatch.setattr(flashcards.llm, "generate_json", AsyncMock(return_value={}))
    cards = [{"front": "Q1", "back": "A1", "topic_index": 0, "difficulty": "easy"}]

    assert await flashcards._filter_grounded(["text"], cards) == []


async def test_dedupe_drops_near_duplicate_embeddings(monkeypatch):
    monkeypatch.setattr(
        flashcards.llm,
        "embed_texts",
        AsyncMock(return_value=[_embedding(0), _embedding(0), _embedding(1)]),
    )
    cards = [
        {"front": "Q1", "back": "A1", "topic_index": 0, "difficulty": "easy"},
        {"front": "Q1 rephrased", "back": "A1", "topic_index": 0, "difficulty": "easy"},
        {"front": "Q2", "back": "A2", "topic_index": 0, "difficulty": "easy"},
    ]

    deduped = await flashcards._dedupe(cards)

    assert deduped == [cards[0], cards[2]]


async def test_generate_flashcards_no_matching_segments_returns_empty(monkeypatch):
    mock_generate = AsyncMock()
    monkeypatch.setattr(flashcards.llm, "generate_json", mock_generate)

    async with async_session() as session:
        video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="t", status="ready")
        session.add(video)
        await session.commit()

        cards = await flashcards.generate_flashcards(
            session,
            video.id,
            count=5,
            scope="whole_video",
            segment_ids=[],
            difficulty="mixed",
            style="mixed",
        )

        assert cards == []
        mock_generate.assert_not_called()

        await session.delete(video)
        await session.commit()


async def test_generate_flashcards_happy_path_maps_segment_and_timestamp(monkeypatch):
    monkeypatch.setattr(
        flashcards.llm,
        "generate_json",
        AsyncMock(
            side_effect=[
                {
                    "cards": [
                        {
                            "front": "What is attention?",
                            "back": "A weighting mechanism.",
                            "topic_index": 0,
                            "difficulty": "easy",
                        },
                        {
                            "front": "Who invented attention?",
                            "back": "Not stated in the video.",
                            "topic_index": 0,
                            "difficulty": "easy",
                        },
                    ]
                },
                {"grounded_card_indices": [0]},
            ]
        ),
    )
    monkeypatch.setattr(flashcards.llm, "embed_texts", AsyncMock(return_value=[_embedding(0)]))

    async with async_session() as session:
        video = Video(
            youtube_id=f"test-{uuid.uuid4().hex[:8]}",
            title="t",
            status="ready",
            transcript=[
                {"start": 5.0, "end": 10.0, "text": "attention weighs tokens by relevance"},
                {"start": 40.0, "end": 45.0, "text": "unrelated later remark"},
            ],
        )
        session.add(video)
        await session.flush()

        segment = TranscriptSegment(
            video_id=video.id,
            order_index=0,
            label="Attention",
            summary="Attention mechanisms explained.",
            start_time=5.0,
            end_time=15.0,
        )
        session.add(segment)
        await session.flush()

        chunk = TranscriptChunk(
            video_id=video.id,
            segment_id=segment.id,
            text="attention weighs tokens by relevance",
            start_time=5.0,
            end_time=10.0,
            embedding=_embedding(0),
        )
        session.add(chunk)
        await session.commit()

        trace: dict = {}
        cards = await flashcards.generate_flashcards(
            session,
            video.id,
            count=5,
            scope="topics",
            segment_ids=[segment.id],
            difficulty="mixed",
            style="mixed",
            trace=trace,
        )

        assert len(cards) == 1
        assert cards[0]["front"] == "What is attention?"
        # The eval trace exposes the ungrounded candidate the user never sees.
        assert [c["front"] for c in trace["candidates"]] == [
            "What is attention?",
            "Who invented attention?",
        ]
        # Identity, not equality: the faithfulness eval tags candidates by id().
        assert [id(c) for c in trace["validated"]] == [id(trace["candidates"][0])]
        assert [id(c) for c in trace["kept"]] == [id(trace["candidates"][0])]
        assert trace["segments"][0].id == segment.id
        # Grounding checks the cited segment's raw transcript, not the summary.
        grounding_prompt = flashcards.llm.generate_json.call_args_list[1].args[1]
        assert "attention weighs tokens by relevance" in grounding_prompt
        assert "unrelated later remark" not in grounding_prompt
        assert cards[0]["segment_id"] == segment.id
        assert float(cards[0]["source_start_time"]) == 5.0
        assert cards[0]["order_index"] == 0

        await session.delete(video)
        await session.commit()
