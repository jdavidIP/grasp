import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.generation import llm
from app.ingestion.slips import slips_in
from app.models.segment import TranscriptSegment
from app.prompts.chat_answer import (
    BROAD_SYSTEM_PROMPT,
    SPECIFIC_SYSTEM_PROMPT,
    build_broad_user_prompt,
    build_specific_user_prompt,
)
from app.prompts.chat_classify import SYSTEM_PROMPT as CLASSIFY_SYSTEM_PROMPT
from app.retrieval.rerank import rerank
from app.retrieval.search import hybrid_search

BROAD_KEYWORDS = (
    "summarize",
    "summary",
    "overview",
    "main points",
    "main point",
    "what is this video about",
    "what's this video about",
)

# ponytail: a hand-picked stopword list, not real NLP — good enough to tell
# "tell me more" from "what did they say about gradient descent".
STOPWORDS = {
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "how",
    "does",
    "do",
    "did",
    "is",
    "are",
    "was",
    "were",
    "this",
    "that",
    "the",
    "a",
    "an",
    "of",
    "in",
    "on",
    "to",
    "and",
    "or",
    "it",
    "its",
    "tell",
    "me",
    "more",
    "they",
    "say",
    "said",
    "can",
    "you",
    "please",
    "explain",
    "about",
    "video",
}

_WORD_RE = re.compile(r"[a-zA-Z']+")


def _has_concrete_noun(question: str) -> bool:
    # ponytail: presence of a content word is treated as "confidently specific" and
    # never escalates to the LLM classifier — misses whole-video questions phrased
    # with real nouns (e.g. "what is this video mainly discussing?", "explain
    # neural networks" meaning the video's whole treatment of it). No usage data
    # exists yet to tune the keyword/stopword lists against real phrasing. If broad
    # questions are getting misrouted in practice, widen the LLM fallback so only
    # the keyword shortcut skips it. `python -m app.eval.chat` measures this: see
    # `routed_broad` for the golden set's broad questions.
    words = _WORD_RE.findall(question.lower())
    return any(len(word) > 3 and word not in STOPWORDS for word in words)


async def classify_question(question: str) -> bool:
    """True for a "broad" (whole-video) question, False for "specific"."""
    lowered = question.lower()
    if any(keyword in lowered for keyword in BROAD_KEYWORDS):
        return True
    if _has_concrete_noun(question):
        return False

    result = await llm.generate_json(CLASSIFY_SYSTEM_PROMPT, question)
    return bool(result.get("broad", False))


async def answer_question(
    session: AsyncSession, video_id: uuid.UUID, question: str, history: list[dict]
) -> dict:
    """Returns {"answer": str, "sources": list[dict], "grounded": bool, "path": str},
    where path is "broad" or "specific". The API response drops `path`."""
    if await classify_question(question):
        return await _answer_broad(session, video_id, question, history) | {"path": "broad"}
    return await _answer_specific(session, video_id, question, history) | {"path": "specific"}


async def _answer_specific(
    session: AsyncSession, video_id: uuid.UUID, question: str, history: list[dict]
) -> dict:
    query_embedding = (await llm.embed_texts([question]))[0]
    candidates = await hybrid_search(session, video_id, question, query_embedding)
    if not candidates:
        return {
            "answer": "This video doesn't seem to cover that.",
            "sources": [],
            "grounded": False,
        }

    top_chunks = await rerank(question, candidates)
    texts = [c.text for c in top_chunks]
    slips = slips_in([s for c in top_chunks for s in c.segment.slips], texts)
    result = await llm.generate_json(
        SPECIFIC_SYSTEM_PROMPT,
        build_specific_user_prompt(question, texts, history, slips),
    )

    sources = [
        {
            "chunk_id": chunk.id,
            "segment_label": chunk.segment.label,
            "start_time": chunk.start_time,
            "end_time": chunk.end_time,
            "text": chunk.text,
        }
        for chunk in top_chunks
    ]
    return {
        "answer": _with_slip_notes(result.get("answer", ""), slips, result.get("slips_used")),
        "sources": sources,
        "grounded": bool(result.get("grounded", False)),
    }


def _with_slip_notes(answer: str, slips: list[dict], used: object) -> str:
    """Appends a note for each known slip the model says its answer relies on, so the
    viewer isn't confused when the video says something else. The model only picks
    the slips: asked to write the note itself, it silently corrected instead (#34)."""
    if not isinstance(used, list):
        return answer
    indexes = [i for i in used if type(i) is int and 0 <= i < len(slips)]
    notes = [
        f'(The video says "{slips[i]["said"]}" here; the speaker means "{slips[i]["meant"]}".)'
        for i in dict.fromkeys(indexes)
    ]
    return " ".join([answer, *notes]) if notes else answer


async def _answer_broad(
    session: AsyncSession, video_id: uuid.UUID, question: str, history: list[dict]
) -> dict:
    result = await session.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.video_id == video_id)
        .order_by(TranscriptSegment.order_index)
    )
    segments = list(result.scalars())
    if not segments:
        return {
            "answer": "This video hasn't been processed yet, so there's nothing to summarize.",
            "sources": [],
            "grounded": False,
        }

    slips = slips_in(
        [s for segment in segments for s in segment.slips], [s.summary for s in segments]
    )
    answer_result = await llm.generate_json(
        BROAD_SYSTEM_PROMPT,
        build_broad_user_prompt(question, [(s.label, s.summary) for s in segments], history, slips),
    )

    sources = [
        {
            "chunk_id": None,
            "segment_label": segment.label,
            "start_time": segment.start_time,
            "end_time": segment.end_time,
            "text": segment.summary,
        }
        for segment in segments
    ]
    return {
        "answer": _with_slip_notes(
            answer_result.get("answer", ""), slips, answer_result.get("slips_used")
        ),
        "sources": sources,
        "grounded": bool(answer_result.get("grounded", False)),
    }
