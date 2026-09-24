import asyncio
import logging
import tempfile
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yt_dlp
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from youtube_transcript_api import (
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)
from yt_dlp.utils import DownloadError

from app.config import settings
from app.db import async_session
from app.generation import llm
from app.ingestion import chunking, segmentation
from app.models.chunk import TranscriptChunk
from app.models.segment import TranscriptSegment
from app.models.video import Video

logger = logging.getLogger(__name__)


class IngestionError(Exception):
    """A handled ingestion failure; its message is stored as videos.error_message."""


def extract_youtube_id(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.hostname in ("youtu.be",):
        video_id = parsed.path.lstrip("/")
        return video_id or None
    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/embed/"):
            return parsed.path.removeprefix("/embed/") or None
    return None


def _video_url(youtube_id: str) -> str:
    return f"https://www.youtube.com/watch?v={youtube_id}"


def _extract_metadata(youtube_id: str) -> dict:
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(_video_url(youtube_id), download=False)
    except DownloadError as e:
        raise IngestionError(str(e)) from e


def _fetch_captions(youtube_id: str) -> list[dict]:
    transcript = YouTubeTranscriptApi().fetch(youtube_id, languages=["en"])
    return [
        {"start": snippet.start, "end": snippet.start + snippet.duration, "text": snippet.text}
        for snippet in transcript
    ]


def _download_audio(youtube_id: str, tmp_dir: str) -> Path:
    opts = {
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
        "outtmpl": str(Path(tmp_dir) / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(_video_url(youtube_id), download=True)
            return Path(ydl.prepare_filename(info))
    except DownloadError as e:
        raise IngestionError(str(e)) from e


async def _fetch_transcript(youtube_id: str) -> tuple[list[dict], str]:
    try:
        cues = await asyncio.to_thread(_fetch_captions, youtube_id)
        if cues:
            return cues, "captions"
        logger.info("captions track for %s was empty, falling back to whisper", youtube_id)
    except (TranscriptsDisabled, NoTranscriptFound, RequestBlocked, VideoUnavailable) as e:
        logger.info(
            "no English captions for %s (%s), falling back to whisper",
            youtube_id,
            type(e).__name__,
        )

    # ponytail: whisper output is used regardless of spoken language — no check that
    # the fallback audio is actually English. Add a language-detect/reject step if
    # non-English videos start producing unusable transcripts.
    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_path = await asyncio.to_thread(_download_audio, youtube_id, tmp_dir)
        cues = await llm.transcribe_audio(audio_path)
    return cues, "whisper"


async def _store_segments_and_chunks(session: AsyncSession, video: Video, cues: list[dict]) -> None:
    segment_dicts = await segmentation.segment_transcript(cues)
    chunk_dicts = await chunking.chunk_transcript(cues, segment_dicts)

    segment_rows = [
        TranscriptSegment(
            order_index=s["order_index"],
            label=s["label"],
            summary=s["summary"],
            start_time=s["start_time"],
            end_time=s["end_time"],
            slips=s["slips"],
        )
        for s in segment_dicts
    ]
    # video.segments was already loaded (lazy="selectin") when this video was fetched,
    # so it's the ORM's source of truth for this relationship in this session — adding
    # rows via session.add_all() instead of through the collection gets their video_id
    # silently nulled out at flush.
    video.segments.extend(segment_rows)
    await session.flush()  # assign real ids for the FK mapping below

    segment_id_by_order_index = {row.order_index: row.id for row in segment_rows}
    chunk_rows = [
        TranscriptChunk(
            video_id=video.id,
            segment_id=segment_id_by_order_index[c["segment_order_index"]],
            text=c["text"],
            start_time=c["start_time"],
            end_time=c["end_time"],
            token_count=c["token_count"],
            embedding=c["embedding"],
        )
        for c in chunk_dicts
    ]
    session.add_all(chunk_rows)


async def run_ingestion(video_id: uuid.UUID) -> None:
    async with async_session() as session:
        video = await session.get(Video, video_id)
        if video is None:
            return
        video.status = "processing"
        await session.commit()

        try:
            metadata = await asyncio.to_thread(_extract_metadata, video.youtube_id)
            duration = metadata.get("duration")
            if duration is None:
                raise IngestionError(
                    "Could not determine this video's duration (it may be a live stream)."
                )
            if duration > settings.max_video_duration_seconds:
                raise IngestionError(
                    f"Video is {duration // 60} minutes long, over the "
                    f"{settings.max_video_duration_seconds // 60}-minute limit."
                )

            video.title = metadata.get("title") or video.youtube_id
            video.channel = metadata.get("uploader") or metadata.get("channel")
            video.duration_seconds = duration
            video.thumbnail_url = metadata.get("thumbnail")

            cues, source = await _fetch_transcript(video.youtube_id)
            if not cues:
                raise IngestionError("No transcript content was found for this video.")

            video.transcript = cues
            video.transcript_source = source

            await _store_segments_and_chunks(session, video, cues)

            video.status = "ready"
        except (IngestionError, llm.LLMError) as e:
            video.status = "failed"
            video.error_message = str(e)
        except Exception:
            logger.exception("ingestion failed unexpectedly for video %s", video_id)
            video.status = "failed"
            video.error_message = "Ingestion failed unexpectedly."

        await session.commit()


async def run_reprocessing(video_id: uuid.UUID) -> None:
    async with async_session() as session:
        video = await session.get(Video, video_id)
        if video is None or video.transcript is None:
            return

        try:
            await session.execute(
                delete(TranscriptSegment).where(TranscriptSegment.video_id == video.id)
            )
            await _store_segments_and_chunks(session, video, video.transcript)
            video.status = "ready"
        except llm.LLMError as e:
            video.status = "failed"
            video.error_message = str(e)
        except Exception:
            logger.exception("reprocessing failed unexpectedly for video %s", video_id)
            video.status = "failed"
            video.error_message = "Reprocessing failed unexpectedly."

        await session.commit()
