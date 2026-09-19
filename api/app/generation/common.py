"""Helpers shared by the flashcard and quiz generation pipelines: segment selection,
per-topic context building, per-segment validation, an over-request buffer, and
embedding-similarity math."""

import asyncio
import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.generation import llm
from app.models.chunk import TranscriptChunk
from app.models.segment import TranscriptSegment
from app.models.video import Video

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


async def segment_transcripts(
    session: AsyncSession, video_id: uuid.UUID, segments: list[TranscriptSegment]
) -> list[str]:
    """Each segment's raw transcript text, in the same order as `segments`."""
    video = await session.get(Video, video_id)
    cues = (video.transcript if video else None) or []
    return [segment_text(cues, s) for s in segments]


async def audit_by_segment(
    items: list[dict],
    transcripts: list[str],
    system_prompt: str,
    build_user_prompt: Callable[[str, list[dict]], str],
    result_key: str,
) -> list[dict]:
    """Keeps the items an LLM audit accepts, in their original order.

    Each item is checked against the full transcript of the segment it cites
    (`topic_index`), one call per cited segment, in parallel. The generator only saw
    summaries plus a few excerpts, so a validator looking at that same thin context
    can neither verify items grounded elsewhere in the segment (it rejects good ones)
    nor catch facts filled in from general knowledge (it keeps bad ones) — issue #16.
    The model answers with the in-group indices it accepts under `result_key`."""
    by_topic: dict[int, list[int]] = {}
    for i, item in enumerate(items):
        by_topic.setdefault(item["topic_index"], []).append(i)

    async def audit(topic_index: int, indices: list[int]) -> list[int]:
        result = await llm.generate_json(
            system_prompt,
            build_user_prompt(transcripts[topic_index], [items[i] for i in indices]),
        )
        accepted = result.get(result_key)
        if not isinstance(accepted, list):
            return []
        return [indices[j] for j in accepted if isinstance(j, int) and 0 <= j < len(indices)]

    kept = await asyncio.gather(*(audit(t, indices) for t, indices in by_topic.items()))
    kept_indices = {i for indices in kept for i in indices}
    return [item for i, item in enumerate(items) if i in kept_indices]


def overgenerate_count(count: int) -> int:
    return count + max(3, round(count * 0.3))
