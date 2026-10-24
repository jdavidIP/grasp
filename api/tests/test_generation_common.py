import uuid
from unittest.mock import AsyncMock

from app.db import async_session
from app.generation import common
from app.models.chunk import TranscriptChunk
from app.models.segment import TranscriptSegment
from app.models.video import Video


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


async def test_audit_by_segment_uses_the_validation_model(monkeypatch):
    mock = AsyncMock(return_value={"accepted": [0]})
    monkeypatch.setattr(common.llm, "generate_json", mock)
    monkeypatch.setattr(common.llm, "VALIDATION_MODEL", "validator-under-test")
    await common.audit_by_segment(
        [{"topic_index": 0}], ["transcript"], "system", lambda t, g: t, "accepted"
    )
    assert mock.call_args.kwargs["model"] == "validator-under-test"


async def test_audit_by_segment_with_no_items_makes_no_calls(monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr(common.llm, "generate_json", mock)
    assert await common.audit_by_segment([], [], "system", lambda t, g: t, "accepted") == []
    mock.assert_not_called()


async def test_item_source_spans_picks_nearest_chunk_and_falls_back_to_segment_span(monkeypatch):
    # The item about "later" text matches the later chunk, not the segment start; a
    # segment with no embedded chunks falls back to its own start.
    monkeypatch.setattr(
        common.llm, "embed_texts", AsyncMock(return_value=[_embedding(1), _embedding(0)])
    )
    async with async_session() as session:
        video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="t", status="ready")
        session.add(video)
        await session.flush()
        with_chunks = TranscriptSegment(
            video_id=video.id, order_index=0, label="a", summary="a", start_time=5.0, end_time=60.0
        )
        without_chunks = TranscriptSegment(
            video_id=video.id, order_index=1, label="b", summary="b", start_time=60.0, end_time=90.0
        )
        session.add_all([with_chunks, without_chunks])
        await session.flush()
        session.add_all(
            [
                TranscriptChunk(
                    video_id=video.id,
                    segment_id=with_chunks.id,
                    text="early",
                    start_time=5.0,
                    end_time=20.0,
                    embedding=_embedding(0),
                ),
                TranscriptChunk(
                    video_id=video.id,
                    segment_id=with_chunks.id,
                    text="later",
                    start_time=40.0,
                    end_time=55.0,
                    embedding=_embedding(1),
                ),
            ]
        )
        await session.commit()

        spans = await common.item_source_spans(
            session, [with_chunks, without_chunks], [(0, "later"), (1, "anything")]
        )

        assert [(float(s), float(e)) for s, e in spans] == [(40.0, 55.0), (60.0, 90.0)]

        await session.delete(video)
        await session.commit()


async def test_item_source_spans_no_items_skips_embedding(monkeypatch):
    embed = AsyncMock()
    monkeypatch.setattr(common.llm, "embed_texts", embed)
    assert await common.item_source_spans(None, [], []) == []
    embed.assert_not_called()
