import uuid
from unittest.mock import AsyncMock

from app.generation import common
from app.models.chunk import TranscriptChunk


def _embedding(*nonzero_indices: int) -> list[float]:
    vec = [0.0] * 1536
    for i in nonzero_indices:
        vec[i] = 1.0
    return vec


def _chunk(text: str, embedding: list[float] | None = None) -> TranscriptChunk:
    return TranscriptChunk(
        id=uuid.uuid4(), text=text, start_time=0.0, end_time=1.0, embedding=embedding
    )


def test_cosine_similarity_identical_vectors_is_one():
    assert common.cosine_similarity(_embedding(0), _embedding(0)) == 1.0


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert common.cosine_similarity(_embedding(0), _embedding(1)) == 0.0


def test_top_chunks_by_centrality_keeps_fewer_than_requested():
    chunks = [_chunk("a", _embedding(0)), _chunk("b", _embedding(1))]
    assert common.top_chunks_by_centrality(chunks, keep=5) == chunks


def test_top_chunks_by_centrality_drops_outlier():
    close_a = _chunk("a", _embedding(0))
    close_b = _chunk("b", _embedding(0, 1))
    outlier = _chunk("c", _embedding(2))
    kept = common.top_chunks_by_centrality([close_a, close_b, outlier], keep=2)
    assert outlier not in kept


def test_overgenerate_count_adds_a_buffer():
    assert common.overgenerate_count(10) >= 13


async def _audit(monkeypatch, items, responses):
    monkeypatch.setattr(common.llm, "generate_json", AsyncMock(side_effect=responses))
    return await common.audit_by_segment(
        items,
        ["seg zero", "seg one"],
        "system",
        lambda transcript, group: transcript,
        "accepted",
    )


async def test_audit_by_segment_maps_group_indices_back_and_keeps_order(monkeypatch):
    items = [{"topic_index": 0}, {"topic_index": 1}, {"topic_index": 0}, {"topic_index": 1}]
    # Segment 0's group is items 0 and 2: accepting its index 1 means item 2.
    # Segment 1's group is items 1 and 3: accepting its index 0 means item 1.
    kept = await _audit(monkeypatch, items, [{"accepted": [1]}, {"accepted": [0]}])
    assert kept == [items[1], items[2]]


async def test_audit_by_segment_ignores_duplicate_and_out_of_range_indices(monkeypatch):
    items = [{"topic_index": 0}, {"topic_index": 0}]
    # A duplicate keeps an item once; out-of-range, negative, and non-int are dropped.
    kept = await _audit(monkeypatch, items, [{"accepted": [0, 0, 5, -1, "1", None]}])
    assert kept == [items[0]]


async def test_audit_by_segment_drops_only_the_group_with_a_malformed_response(monkeypatch):
    items = [{"topic_index": 0}, {"topic_index": 1}]
    kept = await _audit(monkeypatch, items, [{}, {"accepted": [0]}])
    assert kept == [items[1]]


async def test_audit_by_segment_with_no_items_makes_no_calls(monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr(common.llm, "generate_json", mock)
    assert await common.audit_by_segment([], [], "system", lambda t, g: t, "accepted") == []
    mock.assert_not_called()
