"""Helpers shared by the flashcard and quiz generation pipelines: segment selection,
per-topic context building, an over-request buffer, and embedding-similarity math."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import TranscriptChunk
from app.models.segment import TranscriptSegment

VALID_DIFFICULTIES = {"easy", "medium", "hard"}

# ponytail: every segment gets the same 2 excerpts in whole-video context, however
# long it is. Since the #15 segmentation fix, coverage is 46-100% on the eval videos
# and the faithfulness eval shows no harm, but a 28-minute podcast topic is only
# ~15% represented. Upgrade: split a total excerpt budget in proportion to segment
# length, once an eval shows long-segment items failing. The overgenerate/dedupe
# constants below are still hand-picked with no tuning data.
CENTRALITY_CHUNKS_PER_SEGMENT = 2
DEDUPE_SIMILARITY_THRESHOLD = 0.93


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _centroid(vectors: list[list[float]]) -> list[float]:
    dim = len(vectors[0])
    return [sum(v[i] for v in vectors) / len(vectors) for i in range(dim)]


def top_chunks_by_centrality(
    chunks: list[TranscriptChunk], keep: int = CENTRALITY_CHUNKS_PER_SEGMENT
) -> list[TranscriptChunk]:
    """The `keep` chunks whose embeddings are closest to the segment's centroid —
    a cheap stand-in for "most representative of this topic"."""
    embedded = [c for c in chunks if c.embedding is not None]
    if len(embedded) <= keep:
        return embedded
    centroid = _centroid([c.embedding for c in embedded])
    ranked = sorted(embedded, key=lambda c: cosine_similarity(c.embedding, centroid), reverse=True)
    return ranked[:keep]


async def select_segments(
    session: AsyncSession, video_id: uuid.UUID, scope: str, segment_ids: list[uuid.UUID]
) -> list[TranscriptSegment]:
    query = select(TranscriptSegment).where(TranscriptSegment.video_id == video_id)
    if scope == "topics":
        query = query.where(TranscriptSegment.id.in_(segment_ids))
    query = query.order_by(TranscriptSegment.order_index)
    result = await session.execute(query)
    return list(result.scalars())


async def build_topic_contexts(
    session: AsyncSession, segments: list[TranscriptSegment], scope: str
) -> list[tuple[str, str]]:
    """One (label, context text) pair per segment, in the same order as `segments`.

    `topics` scope passes each topic's full transcript text; `whole_video` passes
    summaries plus a few representative excerpts, to keep long videos in-budget.
    """
    chunks_result = await session.execute(
        select(TranscriptChunk)
        .where(TranscriptChunk.segment_id.in_([s.id for s in segments]))
        .order_by(TranscriptChunk.start_time)
    )
    chunks_by_segment: dict[uuid.UUID, list[TranscriptChunk]] = {}
    for chunk in chunks_result.scalars():
        chunks_by_segment.setdefault(chunk.segment_id, []).append(chunk)

    contexts = []
    for segment in segments:
        segment_chunks = chunks_by_segment.get(segment.id, [])
        if scope == "topics":
            excerpt_chunks = segment_chunks
        else:
            excerpt_chunks = top_chunks_by_centrality(segment_chunks)
        excerpts = "\n".join(c.text for c in excerpt_chunks)
        text = (
            f"Summary: {segment.summary}\n\nExcerpts:\n{excerpts}" if excerpts else segment.summary
        )
        contexts.append((segment.label, text))
    return contexts


def segment_text(cues: list[dict], segment: TranscriptSegment) -> str:
    """The raw transcript text inside a segment's time range. Uses cues rather than
    chunks because chunks overlap and would repeat text."""
    start, end = float(segment.start_time), float(segment.end_time)
    return " ".join(c["text"] for c in cues if c["end"] > start and c["start"] < end)


def overgenerate_count(count: int) -> int:
    return count + max(3, round(count * 0.3))
