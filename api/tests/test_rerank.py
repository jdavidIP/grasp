from unittest.mock import AsyncMock

from app.models.chunk import TranscriptChunk
from app.retrieval.rerank import rerank


def _chunk(text: str) -> TranscriptChunk:
    return TranscriptChunk(text=text, start_time=0, end_time=1)


def _chunks(*texts: str) -> list[TranscriptChunk]:
    return [_chunk(t) for t in texts]


async def test_rerank_skips_llm_call_when_already_under_keep(monkeypatch):
    mock_generate = AsyncMock()
    monkeypatch.setattr("app.retrieval.rerank.llm.generate_json", mock_generate)

    chunks = _chunks("a", "b", "c")
    result = await rerank("question", chunks, keep=5)

    assert result == chunks
    mock_generate.assert_not_called()


async def test_rerank_reorders_by_llm_ranking(monkeypatch):
    chunks = _chunks("a", "b", "c", "d", "e", "f")
    monkeypatch.setattr(
        "app.retrieval.rerank.llm.generate_json",
        AsyncMock(return_value={"ranked_indices": [3, 1, 5, 0, 2, 4]}),
    )

    result = await rerank("question", chunks, keep=3)

    assert [c.text for c in result] == ["d", "b", "f"]


async def test_rerank_deduplicates_and_skips_invalid_indices(monkeypatch):
    chunks = _chunks("a", "b", "c", "d", "e", "f")
    monkeypatch.setattr(
        "app.retrieval.rerank.llm.generate_json",
        AsyncMock(return_value={"ranked_indices": [2, 2, 99, "x", 0, 1]}),
    )

    result = await rerank("question", chunks, keep=5)

    assert [c.text for c in result] == ["c", "a", "b"]


async def test_rerank_falls_back_on_malformed_response(monkeypatch):
    chunks = _chunks("a", "b", "c", "d", "e", "f")
    monkeypatch.setattr(
        "app.retrieval.rerank.llm.generate_json",
        AsyncMock(return_value={"unexpected": "shape"}),
    )

    result = await rerank("question", chunks, keep=3)

    assert [c.text for c in result] == ["a", "b", "c"]


async def test_rerank_falls_back_when_no_valid_indices_survive(monkeypatch):
    chunks = _chunks("a", "b", "c", "d", "e", "f")
    monkeypatch.setattr(
        "app.retrieval.rerank.llm.generate_json",
        AsyncMock(return_value={"ranked_indices": [99, "x", -1]}),
    )

    result = await rerank("question", chunks, keep=3)

    assert [c.text for c in result] == ["a", "b", "c"]
