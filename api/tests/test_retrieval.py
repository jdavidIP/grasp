import uuid

from app.db import async_session
from app.models.chunk import TranscriptChunk
from app.models.segment import TranscriptSegment
from app.models.video import Video
from app.retrieval.search import hybrid_search, keyword_search, vector_search


def _embedding(*nonzero_indices: int) -> list[float]:
    vec = [0.0] * 1536
    for i in nonzero_indices:
        vec[i] = 1.0
    return vec


async def test_vector_search_orders_by_similarity_and_scopes_to_video():
    async with async_session() as session:
        video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="t", status="ready")
        other_video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="o", status="ready")
        session.add_all([video, other_video])
        await session.flush()

        segment = TranscriptSegment(
            video_id=video.id, order_index=0, label="Topic", summary="S", start_time=0, end_time=10
        )
        other_segment = TranscriptSegment(
            video_id=other_video.id,
            order_index=0,
            label="Other",
            summary="S",
            start_time=0,
            end_time=10,
        )
        session.add_all([segment, other_segment])
        await session.flush()

        close = TranscriptChunk(
            video_id=video.id,
            segment_id=segment.id,
            text="close",
            start_time=0,
            end_time=1,
            embedding=_embedding(0),
        )
        far = TranscriptChunk(
            video_id=video.id,
            segment_id=segment.id,
            text="far",
            start_time=1,
            end_time=2,
            embedding=_embedding(1),
        )
        other = TranscriptChunk(
            video_id=other_video.id,
            segment_id=other_segment.id,
            text="other video, identical embedding",
            start_time=0,
            end_time=1,
            embedding=_embedding(0),
        )
        session.add_all([close, far, other])
        await session.commit()

        results = await vector_search(session, video.id, _embedding(0), k=5)

        assert [r.text for r in results] == ["close", "far"]
        assert results[0].segment.label == "Topic"

        await session.delete(video)
        await session.delete(other_video)
        await session.commit()


async def test_vector_search_respects_k():
    async with async_session() as session:
        video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="t", status="ready")
        session.add(video)
        await session.flush()

        segment = TranscriptSegment(
            video_id=video.id, order_index=0, label="Topic", summary="S", start_time=0, end_time=10
        )
        session.add(segment)
        await session.flush()

        chunks = [
            TranscriptChunk(
                video_id=video.id,
                segment_id=segment.id,
                text=f"chunk {i}",
                start_time=i,
                end_time=i + 1,
                embedding=_embedding(i % 1536),
            )
            for i in range(5)
        ]
        session.add_all(chunks)
        await session.commit()

        results = await vector_search(session, video.id, _embedding(0), k=2)

        assert len(results) == 2

        await session.delete(video)
        await session.commit()


async def test_keyword_search_ranks_matching_text_first():
    async with async_session() as session:
        video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="t", status="ready")
        session.add(video)
        await session.flush()

        segment = TranscriptSegment(
            video_id=video.id, order_index=0, label="Topic", summary="S", start_time=0, end_time=10
        )
        session.add(segment)
        await session.flush()

        relevant = TranscriptChunk(
            video_id=video.id,
            segment_id=segment.id,
            text="the transformer architecture uses self-attention layers",
            start_time=0,
            end_time=1,
            embedding=_embedding(0),
        )
        irrelevant = TranscriptChunk(
            video_id=video.id,
            segment_id=segment.id,
            text="cooking pasta requires boiling water first",
            start_time=1,
            end_time=2,
            embedding=_embedding(1),
        )
        session.add_all([relevant, irrelevant])
        await session.commit()

        results = await keyword_search(session, video.id, "transformer attention", k=5)

        assert len(results) == 1
        assert results[0].text == relevant.text

        await session.delete(video)
        await session.commit()


async def test_hybrid_search_fuses_vector_and_keyword_results():
    async with async_session() as session:
        video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="t", status="ready")
        session.add(video)
        await session.flush()

        segment = TranscriptSegment(
            video_id=video.id, order_index=0, label="Topic", summary="S", start_time=0, end_time=10
        )
        session.add(segment)
        await session.flush()

        query_embedding = _embedding(0)
        query_text = "python programming tutorial"

        # Top of both vector and keyword rankings.
        both = TranscriptChunk(
            video_id=video.id,
            segment_id=segment.id,
            text="python programming tutorial for beginners",
            start_time=0,
            end_time=1,
            embedding=query_embedding,
        )
        # Keyword match, but a distant embedding.
        keyword_only = TranscriptChunk(
            video_id=video.id,
            segment_id=segment.id,
            text="python programming tutorial, the long way round",
            start_time=1,
            end_time=2,
            embedding=_embedding(1),
        )
        # Close embedding (but not tied with `both` — a tie makes vector rank order
        # between them arbitrary, which can flip the RRF result by a hair), unrelated
        # text.
        vector_only = TranscriptChunk(
            video_id=video.id,
            segment_id=segment.id,
            text="something totally unrelated about gardening",
            start_time=2,
            end_time=3,
            embedding=_embedding(0, 50),
        )
        session.add_all([both, keyword_only, vector_only])
        await session.commit()

        results = await hybrid_search(session, video.id, query_text, query_embedding, k=5)

        result_texts = [r.text for r in results]
        assert both.text in result_texts
        assert keyword_only.text in result_texts
        assert vector_only.text in result_texts
        assert results[0].text == both.text

        await session.delete(video)
        await session.commit()
