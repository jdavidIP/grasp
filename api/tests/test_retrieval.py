import uuid

from app.db import async_session
from app.models.chunk import TranscriptChunk
from app.models.segment import TranscriptSegment
from app.models.video import Video
from app.retrieval.search import vector_search


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
