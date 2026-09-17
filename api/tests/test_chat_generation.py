import uuid
from unittest.mock import AsyncMock

from app.db import async_session
from app.generation import chat
from app.models.chunk import TranscriptChunk
from app.models.segment import TranscriptSegment
from app.models.video import Video


def _chunk(text: str, label: str) -> TranscriptChunk:
    chunk = TranscriptChunk(id=uuid.uuid4(), text=text, start_time=0.0, end_time=1.0)
    chunk.segment = TranscriptSegment(
        label=label, summary="S", start_time=0, end_time=1, order_index=0
    )
    return chunk


async def test_classify_question_broad_keyword_no_llm_call(monkeypatch):
    mock_generate = AsyncMock()
    monkeypatch.setattr(chat.llm, "generate_json", mock_generate)

    assert await chat.classify_question("Can you summarize this video?") is True
    mock_generate.assert_not_called()


async def test_classify_question_specific_with_noun_no_llm_call(monkeypatch):
    mock_generate = AsyncMock()
    monkeypatch.setattr(chat.llm, "generate_json", mock_generate)

    assert await chat.classify_question("What did they say about gradient descent?") is False
    mock_generate.assert_not_called()


async def test_classify_question_ambiguous_falls_back_to_llm(monkeypatch):
    monkeypatch.setattr(chat.llm, "generate_json", AsyncMock(return_value={"broad": True}))

    assert await chat.classify_question("tell me more about that") is True


async def test_answer_specific_no_candidates_returns_not_covered(monkeypatch):
    monkeypatch.setattr(chat.llm, "embed_texts", AsyncMock(return_value=[[0.1] * 1536]))
    monkeypatch.setattr(chat, "hybrid_search", AsyncMock(return_value=[]))
    mock_generate = AsyncMock()
    monkeypatch.setattr(chat.llm, "generate_json", mock_generate)

    result = await chat._answer_specific(None, uuid.uuid4(), "what about gradient descent?", [])

    assert result["grounded"] is False
    assert result["sources"] == []
    mock_generate.assert_not_called()


async def test_answer_specific_happy_path(monkeypatch):
    chunks = [
        _chunk("attention is a mechanism", "Attention"),
        _chunk("it weighs tokens", "Attention"),
    ]
    monkeypatch.setattr(chat.llm, "embed_texts", AsyncMock(return_value=[[0.1] * 1536]))
    monkeypatch.setattr(chat, "hybrid_search", AsyncMock(return_value=chunks))
    monkeypatch.setattr(chat, "rerank", AsyncMock(return_value=chunks))
    monkeypatch.setattr(
        chat.llm,
        "generate_json",
        AsyncMock(return_value={"answer": "Attention weighs tokens.", "grounded": True}),
    )

    result = await chat._answer_specific(None, uuid.uuid4(), "what is attention?", [])

    assert result["answer"] == "Attention weighs tokens."
    assert result["grounded"] is True
    assert len(result["sources"]) == 2
    assert result["sources"][0]["chunk_id"] == chunks[0].id
    assert result["sources"][0]["segment_label"] == "Attention"


async def test_answer_broad_path_uses_segment_summaries(monkeypatch):
    monkeypatch.setattr(
        chat.llm,
        "generate_json",
        AsyncMock(return_value={"answer": "It covers intro and body.", "grounded": True}),
    )

    async with async_session() as session:
        video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="t", status="ready")
        session.add(video)
        await session.flush()

        seg1 = TranscriptSegment(
            video_id=video.id,
            order_index=0,
            label="Intro",
            summary="Intro summary.",
            start_time=0,
            end_time=10,
        )
        seg2 = TranscriptSegment(
            video_id=video.id,
            order_index=1,
            label="Body",
            summary="Body summary.",
            start_time=10,
            end_time=20,
        )
        session.add_all([seg1, seg2])
        await session.commit()

        result = await chat._answer_broad(session, video.id, "what's this video about?", [])

        assert result["answer"] == "It covers intro and body."
        assert len(result["sources"]) == 2
        assert result["sources"][0]["chunk_id"] is None
        assert result["sources"][0]["segment_label"] == "Intro"
        assert result["sources"][0]["text"] == "Intro summary."

        await session.delete(video)
        await session.commit()


async def test_answer_broad_no_segments_skips_llm_call(monkeypatch):
    mock_generate = AsyncMock()
    monkeypatch.setattr(chat.llm, "generate_json", mock_generate)

    async with async_session() as session:
        video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="t", status="ready")
        session.add(video)
        await session.commit()

        result = await chat._answer_broad(session, video.id, "what's this about?", [])

        assert result["grounded"] is False
        assert result["sources"] == []
        mock_generate.assert_not_called()

        await session.delete(video)
        await session.commit()
