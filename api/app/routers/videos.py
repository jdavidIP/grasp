import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.ingestion.videos import extract_youtube_id, run_ingestion, run_reprocessing
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
    try:
        await db.commit()
    except IntegrityError:  # added by a simultaneous request since the check above
        raise HTTPException(
            status_code=409, detail="This video is already in the library."
        ) from None
    await db.refresh(video)

    background_tasks.add_task(run_ingestion, video.id)
    return video


@router.get("/videos/{video_id}", response_model=VideoDetail)
async def get_video(video_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Video:
    video = await db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    return video


@router.post("/videos/{video_id}/reprocess", response_model=VideoListItem, status_code=202)
async def reprocess_video(
    video_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Video:
    # Claim the video in one statement, before looking at anything else: two
    # simultaneous requests can't both pass, and two runs would each delete and
    # rewrite the segments over several minutes. A pending video's ingestion is
    # about to start (startup fails any a restart left stuck).
    video = await db.scalar(
        update(Video)
        .where(Video.id == video_id, Video.status.not_in(("pending", "processing")))
        .values(status="processing")
        .returning(Video)
    )
    if video is None:
        if await db.scalar(select(Video.id).where(Video.id == video_id)) is None:
            raise HTTPException(status_code=404, detail="Video not found.")
        raise HTTPException(status_code=409, detail="This video is already being processed.")
    await db.commit()

    # No stored transcript (the first ingestion failed or was interrupted before
    # fetching one): there's nothing to reprocess, so run the whole ingestion again.
    run = run_reprocessing if video.transcript is not None else run_ingestion
    background_tasks.add_task(run, video.id)
    return video


@router.delete("/videos/{video_id}", status_code=204)
async def delete_video(video_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    video = await db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    await db.delete(video)
    await db.commit()
