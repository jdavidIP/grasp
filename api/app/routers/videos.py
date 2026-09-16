import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.ingestion.videos import extract_youtube_id, run_ingestion
from app.models.video import Video
from app.schemas.video import VideoCreate, VideoDetail, VideoListItem

router = APIRouter()


@router.get("/videos", response_model=list[VideoListItem])
async def list_videos(db: AsyncSession = Depends(get_db)) -> list[Video]:
    result = await db.execute(select(Video).order_by(Video.created_at.desc()))
    return list(result.scalars())


@router.post("/videos", response_model=VideoListItem, status_code=201)
async def create_video(
    payload: VideoCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Video:
    youtube_id = extract_youtube_id(payload.url)
    if youtube_id is None:
        raise HTTPException(
            status_code=400, detail="Could not parse a YouTube video ID from that URL."
        )

    existing = await db.scalar(select(Video).where(Video.youtube_id == youtube_id))
    if existing is not None:
        raise HTTPException(status_code=409, detail="This video is already in the library.")

    video = Video(youtube_id=youtube_id, title=youtube_id, status="pending")
    db.add(video)
    await db.commit()
    await db.refresh(video)

    background_tasks.add_task(run_ingestion, video.id)
    return video


@router.get("/videos/{video_id}", response_model=VideoDetail)
async def get_video(video_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Video:
    video = await db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    return video


@router.delete("/videos/{video_id}", status_code=204)
async def delete_video(video_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    video = await db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    await db.delete(video)
    await db.commit()
