import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import TranscriptChunk

VECTOR_SEARCH_K = 8


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
