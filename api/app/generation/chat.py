import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.generation import llm
from app.ingestion.slips import slips_in
from app.models.chat_message import ChatMessage
from app.models.chunk import TranscriptChunk
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


def _chunk_source(chunk: TranscriptChunk) -> dict:
    return {
        "chunk_id": chunk.id,
        "segment_label": chunk.segment.label,
        "start_time": chunk.start_time,
        "end_time": chunk.end_time,
        "text": chunk.text,
    }


def _segment_source(segment: TranscriptSegment) -> dict:
    return {
        "chunk_id": None,
        "segment_label": segment.label,
        "start_time": segment.start_time,
        "end_time": segment.end_time,
        "text": segment.summary,
    }


async def load_history(session: AsyncSession, video_id: uuid.UUID) -> list[dict]:
    """The video's chat, oldest first, each assistant message with the sources it was
    shown. Rebuilt rather than stored: reprocessing clears the chat, so the cited
    chunks and the video's segments are still the ones each answer saw."""
    result = await session.execute(
        select(ChatMessage).where(ChatMessage.video_id == video_id).order_by(ChatMessage.created_at)
    )
    messages = list(result.scalars())

    chunk_ids = {i for m in messages for i in m.cited_chunk_ids or []}
    chunks: dict[uuid.UUID, TranscriptChunk] = {}
    if chunk_ids:
        result = await session.execute(
            select(TranscriptChunk).where(TranscriptChunk.id.in_(chunk_ids))
        )
        chunks = {c.id: c for c in result.scalars()}

    segments: list[TranscriptSegment] = []
    if any(m.scope == "broad" for m in messages):
        result = await session.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.video_id == video_id)
            .order_by(TranscriptSegment.order_index)
        )
        segments = list(result.scalars())

    def sources(message: ChatMessage) -> list[dict]:
        if message.scope == "broad":
            return [_segment_source(s) for s in segments]
        # A missing id: an answer that committed after a reprocess replaced its chunks.
        return [_chunk_source(chunks[i]) for i in message.cited_chunk_ids or [] if i in chunks]

    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at,
            "sources": sources(m),
            "grounded": m.grounded,
            "slips": m.slips or [],
        }
        for m in messages
    ]


async def classify_question(question: str) -> bool:
    """True for a "broad" (whole-video) question, False for "specific"."""
    # No keyword shortcut: "summarize what they said about X" is specific, and
    # "what will I learn here?" is broad, so wording alone can't decide (#37).
    result = await llm.generate_json(CLASSIFY_SYSTEM_PROMPT, question)
    # Anything but a real `true` (a "false" string, a missing key) means specific.
    return result.get("broad") is True


async def answer_question(
    session: AsyncSession, video_id: uuid.UUID, question: str, history: list[dict]
) -> dict:
    """Returns {"answer": str, "sources": list[dict], "grounded": bool, "slips":
    list[dict], "path": str}, where slips are the known speaker slips the answer
    relies on ([{said, meant}]) and path is "broad" or "specific". The API response
    drops `path`."""
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
            "slips": [],
        }

    top_chunks = await rerank(question, candidates)
    texts = [c.text for c in top_chunks]
    slips = slips_in([s for c in top_chunks for s in c.segment.slips], texts)
    result = await llm.generate_json(
        SPECIFIC_SYSTEM_PROMPT,
        build_specific_user_prompt(question, texts, history, slips),
    )

    sources = [_chunk_source(chunk) for chunk in top_chunks]
    return {
        "answer": result.get("answer", ""),
        "sources": sources,
        "grounded": bool(result.get("grounded", False)),
        "slips": _slips_used(result, slips),
    }


def _slips_used(result: dict, slips: list[dict]) -> list[dict]:
    """The known slips the model says its answer relies on, shown to the viewer so
    they aren't confused when the video says something else. The model only picks
    them: asked to write the note itself, it silently corrected instead (#34). A
    decline relies on none, even when the model lists one."""
    used = result.get("slips_used")
    if not result.get("grounded") or not isinstance(used, list):
        return []
    indexes = [i for i in used if type(i) is int and 0 <= i < len(slips)]
    return [{"said": slips[i]["said"], "meant": slips[i]["meant"]} for i in dict.fromkeys(indexes)]


def with_slip_notes(answer: str, slips: list[dict]) -> str:
    """The answer as the viewer reads it, with a note per slip. Used by the chat eval:
    its judge counts an unexplained correction as unsupported."""
    notes = [
        f'(The video says "{s["said"]}" here; the speaker means "{s["meant"]}".)' for s in slips
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
            "slips": [],
        }

    slips = slips_in(
        [s for segment in segments for s in segment.slips], [s.summary for s in segments]
    )
    answer_result = await llm.generate_json(
        BROAD_SYSTEM_PROMPT,
        build_broad_user_prompt(question, [(s.label, s.summary) for s in segments], history, slips),
    )

    sources = [_segment_source(segment) for segment in segments]
    return {
        "answer": answer_result.get("answer", ""),
        "sources": sources,
        "grounded": bool(answer_result.get("grounded", False)),
        "slips": _slips_used(answer_result, slips),
    }
