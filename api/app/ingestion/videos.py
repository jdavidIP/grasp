import uuid
from urllib.parse import parse_qs, urlparse

from app.db import async_session
from app.models.video import Video


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


async def run_ingestion(video_id: uuid.UUID) -> None:
    async with async_session() as session:
        video = await session.get(Video, video_id)
        if video is None:
            return
        video.status = "ready"
        await session.commit()
