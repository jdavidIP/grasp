import asyncio
import uuid

from sqlalchemy import Text, cast, func, select
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import TranscriptChunk

VECTOR_SEARCH_K = 8
KEYWORD_SEARCH_K = 8
RRF_K = 60  # standard reciprocal-rank-fusion damping constant


async def vector_search(
    session: AsyncSession,
    video_id: uuid.UUID,
    query_embedding: list[float],
    k: int = VECTOR_SEARCH_K,
) -> list[TranscriptChunk]:
    """Nearest chunks to the query embedding, scoped to one video, nearest first."""
    result = await session.execute(
        select(TranscriptChunk)
        .where(TranscriptChunk.video_id == video_id)
        .order_by(TranscriptChunk.embedding.cosine_distance(query_embedding))
        .limit(k)
    )
    return list(result.scalars())


async def keyword_search(
    session: AsyncSession, video_id: uuid.UUID, query: str, k: int = KEYWORD_SEARCH_K
) -> list[TranscriptChunk]:
    """Postgres full-text search over a video's chunks, best rank first.

    Matches chunks containing ANY of the query's terms, ranked by ts_rank (more
    and rarer matches rank higher). plainto_tsquery alone ANDs every term, which
    for natural-language questions matched nothing on 24/26 golden questions and
    made hybrid search silently equal to pure vector search."""
    and_query = cast(func.plainto_tsquery("english", query), Text)
    ts_query = cast(func.replace(and_query, " & ", " | "), TSQUERY)
    result = await session.execute(
        select(TranscriptChunk)
        .where(TranscriptChunk.video_id == video_id)
        .where(TranscriptChunk.tsv.op("@@")(ts_query))
        .order_by(func.ts_rank(TranscriptChunk.tsv, ts_query).desc())
        .limit(k)
    )
    return list(result.scalars())


async def hybrid_search(
    session: AsyncSession,
    video_id: uuid.UUID,
    query: str,
    query_embedding: list[float],
    k: int = VECTOR_SEARCH_K,
) -> list[TranscriptChunk]:
    """Fuses vector and keyword search results via Reciprocal Rank Fusion — helps
    when the question contains names or jargon the embedding flattens."""
    vector_results, keyword_results = await asyncio.gather(
        vector_search(session, video_id, query_embedding, k=k),
        keyword_search(session, video_id, query, k=k),
    )

    scores: dict[uuid.UUID, float] = {}
    chunks_by_id: dict[uuid.UUID, TranscriptChunk] = {}
    for results in (vector_results, keyword_results):
        for rank, chunk in enumerate(results):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1 / (RRF_K + rank + 1)
            chunks_by_id[chunk.id] = chunk

    ranked_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    return [chunks_by_id[cid] for cid in ranked_ids[:k]]
