"""The only module allowed to call the OpenAI client directly (per CLAUDE.md)."""

import json
import logging
import time
from pathlib import Path

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

WHISPER_MODEL = "whisper-1"
EMBEDDING_MODEL = "text-embedding-3-small"
GENERATION_MODEL = "gpt-4o-mini"

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key, max_retries=3, timeout=120.0)
    return _client


async def transcribe_audio(audio_path: Path) -> list[dict]:
    """Returns cues in the same `{start, end, text}` shape as the captions path."""
    started = time.monotonic()
    with audio_path.open("rb") as audio_file:
        transcription = await _get_client().audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )
    elapsed = time.monotonic() - started
    logger.info(
        "whisper transcription complete file=%s bytes=%d elapsed=%.1fs",
        audio_path.name,
        audio_path.stat().st_size,
        elapsed,
    )
    return [
        {"start": segment.start, "end": segment.end, "text": segment.text.strip()}
        for segment in transcription.segments or []
    ]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-embeds texts, preserving input order."""
    if not texts:
        return []
    started = time.monotonic()
    response = await _get_client().embeddings.create(model=EMBEDDING_MODEL, input=texts)
    elapsed = time.monotonic() - started
    logger.info("embedded %d texts in %.1fs", len(texts), elapsed)
    return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]


async def generate_json(system_prompt: str, user_prompt: str) -> dict:
    """Runs a chat completion constrained to JSON output and parses the result."""
    started = time.monotonic()
    response = await _get_client().chat.completions.create(
        model=GENERATION_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    elapsed = time.monotonic() - started
    usage = response.usage
    logger.info(
        "chat completion complete model=%s tokens=%s elapsed=%.1fs",
        GENERATION_MODEL,
        usage.total_tokens if usage else "unknown",
        elapsed,
    )
    return json.loads(response.choices[0].message.content)
