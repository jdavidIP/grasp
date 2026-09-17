import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.generation import llm
from app.models.chunk import TranscriptChunk
from app.models.segment import TranscriptSegment
from app.prompts.flashcards import (
    GENERATION_SYSTEM_PROMPT,
    GROUNDING_SYSTEM_PROMPT,
    build_generation_user_prompt,
    build_grounding_user_prompt,
)

VALID_DIFFICULTIES = {"easy", "medium", "hard"}

# ponytail: representative-chunk count for whole-video context, and the
# overgenerate/dedupe constants below, are hand-picked with no tuning data yet.
# Revisit against Phase 7's golden set if card quality or yield looks off.
CENTRALITY_CHUNKS_PER_SEGMENT = 2
DEDUPE_SIMILARITY_THRESHOLD = 0.93


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _centroid(vectors: list[list[float]]) -> list[float]:
    dim = len(vectors[0])
    return [sum(v[i] for v in vectors) / len(vectors) for i in range(dim)]


def _top_chunks_by_centrality(
    chunks: list[TranscriptChunk], keep: int = CENTRALITY_CHUNKS_PER_SEGMENT
) -> list[TranscriptChunk]:
    """The `keep` chunks whose embeddings are closest to the segment's centroid —
    a cheap stand-in for "most representative of this topic"."""
    embedded = [c for c in chunks if c.embedding is not None]
    if len(embedded) <= keep:
        return embedded
    centroid = _centroid([c.embedding for c in embedded])
    ranked = sorted(embedded, key=lambda c: _cosine_similarity(c.embedding, centroid), reverse=True)
    return ranked[:keep]


async def _select_segments(
    session: AsyncSession, video_id: uuid.UUID, scope: str, segment_ids: list[uuid.UUID]
) -> list[TranscriptSegment]:
    query = select(TranscriptSegment).where(TranscriptSegment.video_id == video_id)
    if scope == "topics":
        query = query.where(TranscriptSegment.id.in_(segment_ids))
    query = query.order_by(TranscriptSegment.order_index)
    result = await session.execute(query)
    return list(result.scalars())


async def _build_topic_contexts(
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
            excerpt_chunks = _top_chunks_by_centrality(segment_chunks)
        excerpts = "\n".join(c.text for c in excerpt_chunks)
        text = (
            f"Summary: {segment.summary}\n\nExcerpts:\n{excerpts}" if excerpts else segment.summary
        )
        contexts.append((segment.label, text))
    return contexts


def _overgenerate_count(count: int) -> int:
    return count + max(3, round(count * 0.3))


async def _generate_candidates(
    count: int, difficulty: str, style: str, topics: list[tuple[str, str]]
) -> list[dict]:
    result = await llm.generate_json(
        GENERATION_SYSTEM_PROMPT,
        build_generation_user_prompt(_overgenerate_count(count), difficulty, style, topics),
    )
    raw_cards = result.get("cards")
    if not isinstance(raw_cards, list):
        return []

    cards = []
    for card in raw_cards:
        if not isinstance(card, dict):
            continue
        front, back = card.get("front"), card.get("back")
        topic_index = card.get("topic_index")
        if not isinstance(front, str) or not front.strip():
            continue
        if not isinstance(back, str) or not back.strip():
            continue
        if not isinstance(topic_index, int) or not 0 <= topic_index < len(topics):
            continue
        card_difficulty = card.get("difficulty")
        if card_difficulty not in VALID_DIFFICULTIES:
            card_difficulty = difficulty if difficulty in VALID_DIFFICULTIES else "medium"
        cards.append(
            {
                "front": front.strip(),
                "back": back.strip(),
                "topic_index": topic_index,
                "difficulty": card_difficulty,
            }
        )
    return cards


async def _filter_grounded(topics: list[tuple[str, str]], cards: list[dict]) -> list[dict]:
    if not cards:
        return []
    result = await llm.generate_json(
        GROUNDING_SYSTEM_PROMPT, build_grounding_user_prompt(topics, cards)
    )
    grounded_indices = result.get("grounded_card_indices")
    if not isinstance(grounded_indices, list):
        return []
    return [cards[i] for i in grounded_indices if isinstance(i, int) and 0 <= i < len(cards)]


async def _dedupe(cards: list[dict]) -> list[dict]:
    if len(cards) < 2:
        return cards
    embeddings = await llm.embed_texts([f"{c['front']} {c['back']}" for c in cards])

    kept: list[dict] = []
    kept_embeddings: list[list[float]] = []
    for card, embedding in zip(cards, embeddings, strict=True):
        if any(
            _cosine_similarity(embedding, kept_embedding) >= DEDUPE_SIMILARITY_THRESHOLD
            for kept_embedding in kept_embeddings
        ):
            continue
        kept.append(card)
        kept_embeddings.append(embedding)
    return kept


async def generate_flashcards(
    session: AsyncSession,
    video_id: uuid.UUID,
    count: int,
    scope: str,
    segment_ids: list[uuid.UUID],
    difficulty: str,
    style: str,
) -> list[dict]:
    """Returns up to `count` validated cards, each with `front`, `back`,
    `segment_id`, `source_start_time`, `difficulty`, `order_index`. May return
    fewer than `count` if generation and validation don't yield enough —
    ponytail: no regeneration retry loop yet, add one if yield is a problem."""
    segments = await _select_segments(session, video_id, scope, segment_ids)
    if not segments:
        return []

    topics = await _build_topic_contexts(session, segments, scope)
    candidates = await _generate_candidates(count, difficulty, style, topics)
    grounded = await _filter_grounded(topics, candidates)
    deduped = await _dedupe(grounded)

    cards = []
    for order_index, card in enumerate(deduped[:count]):
        segment = segments[card["topic_index"]]
        cards.append(
            {
                "front": card["front"],
                "back": card["back"],
                "segment_id": segment.id,
                "source_start_time": segment.start_time,
                "difficulty": card["difficulty"],
                "order_index": order_index,
            }
        )
    return cards
