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


@pytest.mark.parametrize(
    ("question", "broad"),
    [
        # Keyword-worded but scoped to one topic, and naturally worded but whole-video:
        # both used to be routed by wording alone (#37).
        ("Summarize what they said about gradient descent.", False),
        ("What will I learn from this tutorial?", True),
    ],
)
async def test_classify_question_always_asks_the_classifier(monkeypatch, question, broad):
    mock_generate = AsyncMock(return_value={"broad": broad})
    monkeypatch.setattr(chat.llm, "generate_json", mock_generate)

    assert await chat.classify_question(question) is broad
    mock_generate.assert_awaited_once()


@pytest.mark.parametrize("result", [{"broad": "false"}, {}])
async def test_classify_question_defaults_to_specific(monkeypatch, result):
    monkeypatch.setattr(chat.llm, "generate_json", AsyncMock(return_value=result))

    assert await chat.classify_question("q") is False


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


def test_slips_used_returns_each_slip_the_model_relied_on():
    slips = [
        {"said": "angle brackets", "meant": "square brackets", "reason": "r"},
        {"said": "a", "meant": "b", "reason": "r"},
    ]

    def used(indexes: object, grounded: bool = True) -> list[dict]:
        return chat._slips_used({"grounded": grounded, "slips_used": indexes}, slips)

    assert used([0, 0]) == [{"said": "angle brackets", "meant": "square brackets"}]
    # Out-of-range, non-int, and bool indexes from the model are ignored.
    assert used([5, "0", True]) == []
    assert used(None) == []
    # A decline relies on no slip even if the model still lists one (#34).
    assert used([0], grounded=False) == []


def test_with_slip_notes_formats_what_the_user_sees():
    # The chat eval judges this text, so it must match the note the answer used to carry.
    slips = [{"said": "angle brackets", "meant": "square brackets"}]
    assert chat.with_slip_notes("A.", slips) == (
        'A. (The video says "angle brackets" here; the speaker means "square brackets".)'
    )
    assert chat.with_slip_notes("A.", []) == "A."


async def test_answer_specific_returns_slips_apart_from_the_answer(monkeypatch):
    slip = {"said": "values from 0 to 3", "meant": "values from 0 to 2", "reason": "r"}
    chunks = [_chunk("values from 0 to 3", "Loops", slips=[slip])]
    monkeypatch.setattr(chat.llm, "embed_texts", AsyncMock(return_value=[[0.1] * 1536]))
    monkeypatch.setattr(chat, "hybrid_search", AsyncMock(return_value=chunks))
    monkeypatch.setattr(chat, "rerank", AsyncMock(return_value=chunks))
    monkeypatch.setattr(
        chat.llm,
        "generate_json",
        AsyncMock(
            return_value={"answer": "It prints 0 to 2.", "grounded": True, "slips_used": [0]}
        ),
    )

    result = await chat._answer_specific(None, uuid.uuid4(), "what does range(3) give?", [])

    assert result["answer"] == "It prints 0 to 2."
    assert result["slips"] == [{"said": "values from 0 to 3", "meant": "values from 0 to 2"}]


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
