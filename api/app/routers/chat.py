import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.generation.chat import answer_question
from app.models.chat_message import ChatMessage
from app.models.video import Video
from app.schemas.chat import ChatMessageOut, ChatRequest, ChatResponse

router = APIRouter()

HISTORY_LIMIT = 10


@router.get("/videos/{video_id}/chat", response_model=list[ChatMessageOut])
async def get_chat_history(
    video_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[ChatMessage]:
    if await db.get(Video, video_id) is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    result = await db.execute(
        select(ChatMessage).where(ChatMessage.video_id == video_id).order_by(ChatMessage.created_at)
    )
    return list(result.scalars())


@router.post("/videos/{video_id}/chat", response_model=ChatResponse)
async def send_chat_message(
    video_id: uuid.UUID, payload: ChatRequest, db: AsyncSession = Depends(get_db)
) -> ChatResponse:
    video = await db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.video_id == video_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(HISTORY_LIMIT)
    )
    history = [
        {"role": m.role, "content": m.content} for m in reversed(history_result.scalars().all())
    ]

    # Postgres's now()/server_default is transaction-scoped, not statement-scoped —
    # both messages would get an identical created_at within this one commit, making
    # their order ambiguous. Set explicit, strictly-increasing timestamps instead.
    db.add(
        ChatMessage(
            video_id=video_id, role="user", content=payload.message, created_at=datetime.now(UTC)
        )
    )

    result = await answer_question(db, video_id, payload.message, history)

    cited_chunk_ids = [s["chunk_id"] for s in result["sources"] if s["chunk_id"] is not None]
    db.add(
        ChatMessage(
            video_id=video_id,
            role="assistant",
            content=result["answer"],
            cited_chunk_ids=cited_chunk_ids or None,
            created_at=datetime.now(UTC),
        )
    )
    await db.commit()

    return ChatResponse(**result)


@router.delete("/videos/{video_id}/chat", status_code=204)
async def clear_chat_history(video_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    if await db.get(Video, video_id) is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    await db.execute(delete(ChatMessage).where(ChatMessage.video_id == video_id))
    await db.commit()
