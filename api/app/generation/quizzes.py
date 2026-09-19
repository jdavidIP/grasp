import random
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
from app.prompts.quizzes import (
    GENERATION_SYSTEM_PROMPT,
    VALIDATION_SYSTEM_PROMPT,
    build_generation_user_prompt,
    build_validation_user_prompt,
)

VALID_QUESTION_TYPES = {"multiple_choice", "multi_select", "true_false"}
SELECT_ALL_SUFFIX = "Select all that apply."


def _parse_options(raw_options: object, options_per_question: int) -> list[dict] | None:
    """Well-formed, non-duplicate options of exactly the requested count, or None."""
    if not isinstance(raw_options, list) or len(raw_options) != options_per_question:
        return None
    options = []
    for raw in raw_options:
        if not isinstance(raw, dict):
            return None
        text, is_correct = raw.get("text"), raw.get("is_correct")
        if not isinstance(text, str) or not text.strip() or not isinstance(is_correct, bool):
            return None
        options.append({"text": text.strip(), "is_correct": is_correct})
    if len({o["text"].casefold() for o in options}) != len(options):
        return None
    return options


def _parse_question(raw: object, options_per_question: int, topic_count: int) -> dict | None:
    """Validates one raw model question and normalizes it, or returns None to drop it.

    Enforces the answer-key rules from docs/DATA_MODEL.md: multiple_choice has exactly
    one correct option; multi_select has at least one correct and one incorrect;
    true_false is built here as True/False so the model can't get its options wrong.
    """
    if not isinstance(raw, dict):
        return None
    question_type = raw.get("type")
    prompt, explanation = raw.get("prompt"), raw.get("explanation")
    topic_index = raw.get("topic_index")
    if question_type not in VALID_QUESTION_TYPES:
        return None
    if not isinstance(prompt, str) or not prompt.strip():
        return None
    if not isinstance(explanation, str) or not explanation.strip():
        return None
    if not isinstance(topic_index, int) or not 0 <= topic_index < topic_count:
        return None

    prompt = prompt.strip()
    if question_type == "true_false":
        answer_is_true = raw.get("answer_is_true")
        if not isinstance(answer_is_true, bool):
            return None
        options = [
            {"text": "True", "is_correct": answer_is_true},
            {"text": "False", "is_correct": not answer_is_true},
        ]
    else:
        options = _parse_options(raw.get("options"), options_per_question)
        if options is None:
            return None
        correct_count = sum(o["is_correct"] for o in options)
        if question_type == "multiple_choice" and correct_count != 1:
            return None
        if question_type == "multi_select":
            if correct_count == 0 or correct_count == len(options):
                return None
            if "select all that apply" not in prompt.casefold():
                prompt = f"{prompt} {SELECT_ALL_SUFFIX}"

    return {
        "question_type": question_type,
        "prompt": prompt,
        "explanation": explanation.strip(),
        "topic_index": topic_index,
        "options": options,
        "difficulty": raw.get("difficulty"),
    }


async def _generate_candidates(
    count: int,
    difficulty: str,
    question_types: list[str],
    options_per_question: int,
    topics: list[tuple[str, str]],
    other_topics: list[tuple[str, str]],
) -> list[dict]:
    result = await llm.generate_json(
        GENERATION_SYSTEM_PROMPT,
        build_generation_user_prompt(
            overgenerate_count(count),
            difficulty,
            question_types,
            options_per_question,
            topics,
            other_topics,
        ),
    )
    raw_questions = result.get("questions")
    if not isinstance(raw_questions, list):
        return []

    fallback_difficulty = difficulty if difficulty in VALID_DIFFICULTIES else "medium"
    questions = []
    for raw in raw_questions:
        question = _parse_question(raw, options_per_question, len(topics))
        if question is None or question["question_type"] not in question_types:
            continue
        if question["difficulty"] not in VALID_DIFFICULTIES:
            question["difficulty"] = fallback_difficulty
        questions.append(question)
    return questions


async def _filter_valid(
    topics: list[tuple[str, str]], other_topics: list[tuple[str, str]], questions: list[dict]
) -> list[dict]:
    """LLM audit: keeps only questions whose key is supported by the cited topic and
    whose distractors are verifiably wrong (not arguably correct)."""
    if not questions:
        return []
    result = await llm.generate_json(
        VALIDATION_SYSTEM_PROMPT,
        build_validation_user_prompt(topics + other_topics, questions),
    )
    valid_indices = result.get("valid_question_indices")
    if not isinstance(valid_indices, list):
        return []
    return [questions[i] for i in valid_indices if isinstance(i, int) and 0 <= i < len(questions)]


async def _dedupe(questions: list[dict]) -> list[dict]:
    if len(questions) < 2:
        return questions
    embeddings = await llm.embed_texts([q["prompt"] for q in questions])

    kept: list[dict] = []
    kept_embeddings: list[list[float]] = []
    for question, embedding in zip(questions, embeddings, strict=True):
        if any(
            cosine_similarity(embedding, kept_embedding) >= DEDUPE_SIMILARITY_THRESHOLD
            for kept_embedding in kept_embeddings
        ):
            continue
        kept.append(question)
        kept_embeddings.append(embedding)
    return kept


def _ordered_options(question: dict) -> list[dict]:
    """Shuffles choice options so the model's habit of listing the correct answer in
    a fixed slot doesn't leak; true/false keeps its natural True, False order."""
    options = list(question["options"])
    if question["question_type"] != "true_false":
        random.shuffle(options)
    return [{**o, "order_index": i} for i, o in enumerate(options)]


async def generate_quiz(
    session: AsyncSession,
    video_id: uuid.UUID,
    count: int,
    scope: str,
    segment_ids: list[uuid.UUID],
    question_types: list[str],
    options_per_question: int,
    difficulty: str,
    trace: dict | None = None,
) -> list[dict]:
    """Returns up to `count` validated questions, each with `question_type`, `prompt`,
    `explanation`, `segment_id`, `source_start_time`, `difficulty`, `order_index`, and
    `options` (each `text`, `is_correct`, `order_index`). The answer key comes from
    generation, so grading needs no LLM call. May return fewer than `count` if
    generation and validation don't yield enough —
    ponytail: no regeneration retry loop yet, add one if yield is a problem.
    If `trace` is given, it is filled with the pipeline's intermediate state for the
    offline eval: `segments`, `candidates` (parsed model output before validation),
    `validated` (those the LLM validation pass accepted), and `kept` (the same
    candidate objects that also survived dedupe and the count cap)."""
    segments = await select_segments(session, video_id, scope, segment_ids)
    if not segments:
        return []

    other_topics: list[tuple[str, str]] = []
    if scope == "topics":
        all_segments = await select_segments(session, video_id, "whole_video", [])
        selected_ids = set(segment_ids)
        other_topics = [(s.label, s.summary) for s in all_segments if s.id not in selected_ids]

    topics = await build_topic_contexts(session, segments, scope)
    candidates = await _generate_candidates(
        count, difficulty, question_types, options_per_question, topics, other_topics
    )
    valid = await _filter_valid(topics, other_topics, candidates)
    deduped = await _dedupe(valid)
    if trace is not None:
        trace.update(
            segments=segments, candidates=candidates, validated=valid, kept=deduped[:count]
        )

    questions = []
    for order_index, question in enumerate(deduped[:count]):
        segment = segments[question["topic_index"]]
        questions.append(
            {
                "question_type": question["question_type"],
                "prompt": question["prompt"],
                "explanation": question["explanation"],
                "segment_id": segment.id,
                "source_start_time": segment.start_time,
                "difficulty": question["difficulty"],
                "order_index": order_index,
                "options": _ordered_options(question),
            }
        )
    return questions
