import asyncio
import logging
import tempfile
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yt_dlp
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
        return cues, "captions"
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
            if duration and duration > settings.max_video_duration_seconds:
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
            video.status = "ready"
        except IngestionError as e:
            video.status = "failed"
            video.error_message = str(e)
        except Exception:
            logger.exception("ingestion failed unexpectedly for video %s", video_id)
            video.status = "failed"
            video.error_message = "Ingestion failed unexpectedly."

        await session.commit()
