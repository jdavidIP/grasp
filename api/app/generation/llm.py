import logging
import time
from pathlib import Path

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

WHISPER_MODEL = "whisper-1"

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key, max_retries=3, timeout=120.0)
    return _client


async def transcribe_audio(audio_path: Path) -> str:
    """The only place in the app allowed to call the OpenAI audio API directly."""
    started = time.monotonic()
    with audio_path.open("rb") as audio_file:
        transcription = await _get_client().audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=audio_file,
        )
    elapsed = time.monotonic() - started
    logger.info(
        "whisper transcription complete file=%s bytes=%d elapsed=%.1fs",
        audio_path.name,
        audio_path.stat().st_size,
        elapsed,
    )
    return transcription.text
