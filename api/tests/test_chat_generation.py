import uuid
from unittest.mock import AsyncMock

import pytest

from app.db import async_session
from app.generation import chat
from app.models.chunk import TranscriptChunk
from app.models.segment import TranscriptSegment
from app.models.video import Video


def _chunk(text: str, label: str, slips: list[dict] | None = None) -> TranscriptChunk:
    chunk = TranscriptChunk(id=uuid.uuid4(), text=text, start_time=0.0, end_time=1.0)
    chunk.segment = TranscriptSegment(
        label=label, summary="S", start_time=0, end_time=1, order_index=0, slips=slips or []
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


@pytest.mark.parametrize("broad", [True, False])
async def test_answer_question_reports_its_path_even_with_no_sources(monkeypatch, broad):
    # Both paths can return no sources (an unprocessed video, no retrieval hits), so the
    # path can't be inferred from the sources and has to be reported.
    monkeypatch.setattr(chat, "classify_question", AsyncMock(return_value=broad))
    monkeypatch.setattr(chat.llm, "embed_texts", AsyncMock(return_value=[[0.1] * 1536]))
    monkeypatch.setattr(chat, "hybrid_search", AsyncMock(return_value=[]))

    async with async_session() as session:
        result = await chat.answer_question(session, uuid.uuid4(), "q", [])

    assert result["sources"] == []
    assert result["path"] == ("broad" if broad else "specific")


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


async def test_answer_specific_tells_the_model_the_slips_in_its_excerpts(monkeypatch):
    slips = [
        {"said": "the Soviet Union invaded Ukraine", "meant": "Russia invaded Ukraine"},
        {"said": "at America", "meant": "Latin America"},  # same segment, not in the excerpt
    ]
    chunks = [_chunk("part of the reason the Soviet Union invaded Ukraine.", "Overview", slips)]
    monkeypatch.setattr(chat.llm, "embed_texts", AsyncMock(return_value=[[0.1] * 1536]))
    monkeypatch.setattr(chat, "hybrid_search", AsyncMock(return_value=chunks))
    monkeypatch.setattr(chat, "rerank", AsyncMock(return_value=chunks))
    mock_generate = AsyncMock(return_value={"answer": "a", "grounded": True})
    monkeypatch.setattr(chat.llm, "generate_json", mock_generate)

    await chat._answer_specific(None, uuid.uuid4(), "why was Ukraine invaded?", [])

    user_prompt = mock_generate.await_args.args[1]
    assert (
        'Slip 0: the transcript says "the Soviet Union invaded Ukraine"; '
        'the speaker means "Russia invaded Ukraine".'
    ) in user_prompt
    assert "Latin America" not in user_prompt


def test_with_slip_notes_appends_a_note_per_slip_the_model_used():
    slips = [{"said": "angle brackets", "meant": "square brackets"}, {"said": "a", "meant": "b"}]
    note = '(The video says "angle brackets" here; the speaker means "square brackets".)'

    assert chat._with_slip_notes("Use square brackets.", slips, [0, 0]) == (
        f"Use square brackets. {note}"
    )
    # Out-of-range, non-int, and bool indexes from the model are ignored.
    assert chat._with_slip_notes("A.", slips, [5, "0", True]) == "A."
    assert chat._with_slip_notes("A.", slips, []) == "A."
    assert chat._with_slip_notes("A.", slips, None) == "A."


async def test_answer_specific_adds_no_slip_block_when_there_are_none(monkeypatch):
    chunks = [_chunk("attention is a mechanism", "Attention")]
    monkeypatch.setattr(chat.llm, "embed_texts", AsyncMock(return_value=[[0.1] * 1536]))
    monkeypatch.setattr(chat, "hybrid_search", AsyncMock(return_value=chunks))
    monkeypatch.setattr(chat, "rerank", AsyncMock(return_value=chunks))
    mock_generate = AsyncMock(return_value={"answer": "a", "grounded": True})
    monkeypatch.setattr(chat.llm, "generate_json", mock_generate)

    await chat._answer_specific(None, uuid.uuid4(), "what is attention?", [])

    assert "Known speaker slips" not in mock_generate.await_args.args[1]


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
