import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.generation import llm
from app.generation.common import (
    DEDUPE_SIMILARITY_THRESHOLD,
    VALID_DIFFICULTIES,
    build_topic_contexts,
    cosine_similarity,
    overgenerate_count,
    select_segments,
)
from app.prompts.flashcards import (
    GENERATION_SYSTEM_PROMPT,
    GROUNDING_SYSTEM_PROMPT,
    build_generation_user_prompt,
    build_grounding_user_prompt,
)


async def _generate_candidates(
    count: int, difficulty: str, style: str, topics: list[tuple[str, str]]
) -> list[dict]:
    result = await llm.generate_json(
        GENERATION_SYSTEM_PROMPT,
        build_generation_user_prompt(overgenerate_count(count), difficulty, style, topics),
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
            cosine_similarity(embedding, kept_embedding) >= DEDUPE_SIMILARITY_THRESHOLD
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
    trace: dict | None = None,
) -> list[dict]:
    """Returns up to `count` validated cards, each with `front`, `back`,
    `segment_id`, `source_start_time`, `difficulty`, `order_index`. May return
    fewer than `count` if generation and validation don't yield enough —
    ponytail: no regeneration retry loop yet, add one if yield is a problem.
    If `trace` is given, it is filled with the pipeline's intermediate state for the
    offline eval: `segments`, `candidates` (parsed model output before validation),
    `validated` (those the LLM validation pass accepted), and `kept` (the same
    candidate objects that also survived dedupe and the count cap)."""
    segments = await select_segments(session, video_id, scope, segment_ids)
    if not segments:
        return []

    topics = await build_topic_contexts(session, segments, scope)
    candidates = await _generate_candidates(count, difficulty, style, topics)
    grounded = await _filter_grounded(topics, candidates)
    deduped = await _dedupe(grounded)
    if trace is not None:
        trace.update(
            segments=segments, candidates=candidates, validated=grounded, kept=deduped[:count]
        )

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
