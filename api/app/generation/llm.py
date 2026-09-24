"""The only module allowed to call the OpenAI client directly (per CLAUDE.md)."""

import json
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

import openai
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

WHISPER_MODEL = "whisper-1"
EMBEDDING_MODEL = "text-embedding-3-small"
GENERATION_MODEL = "gpt-4o-mini"
EVAL_MODEL = "gpt-4o"
SLIP_CHECK_MODEL = "gpt-4o"

_client: AsyncOpenAI | None = None

Usage = dict[str, dict[str, int]]
_usage: ContextVar[Usage | None] = ContextVar("llm_usage", default=None)


class LLMError(Exception):
    """An OpenAI call failed. The message is written for a user, not a stack trace:
    ingestion stores it verbatim as `videos.error_message`, and the app-level handler
    in main.py returns it verbatim as a 503 `detail`."""


@contextmanager
def track_usage(totals: Usage | None = None) -> Iterator[Usage]:
    """Totals tokens per model, as {model: {calls, prompt_tokens, completion_tokens}},
    for every call made inside the block, including tasks spawned from it (they
    inherit the same dict). Pass an earlier block's dict to keep adding to it. Blocks
    don't nest: an inner block's calls count only toward the inner totals."""
    if totals is None:
        totals = {}
    token = _usage.set(totals)
    try:
        yield totals
    finally:
        _usage.reset(token)


def _record_usage(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    totals = _usage.get()
    if totals is None:
        return
    entry = totals.setdefault(model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0})
    entry["calls"] += 1
    entry["prompt_tokens"] += prompt_tokens
    entry["completion_tokens"] += completion_tokens


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key, max_retries=3, timeout=120.0)
    return _client


def _user_message(error: openai.OpenAIError) -> str:
    """Translates an OpenAI SDK exception into a cause-specific, user-facing message.
    Order matters: a subclass is checked before the parent class it derives from
    (AuthenticationError and RateLimitError are APIStatusError; APITimeoutError is
    APIConnectionError)."""
    if isinstance(error, openai.AuthenticationError):
        return "OpenAI rejected the API key. Check the OPENAI_API_KEY setting."
    if isinstance(error, openai.RateLimitError):
        return "Hit an OpenAI rate limit or quota. Try again in a moment."
    if isinstance(error, openai.APITimeoutError):
        return "OpenAI didn't respond in time. Try again."
    if isinstance(error, openai.APIConnectionError):
        return "Could not reach OpenAI. Check the network connection."
    if isinstance(error, openai.APIStatusError):
        return "OpenAI is temporarily unavailable. Try again shortly."
    return "The OpenAI request failed."


async def transcribe_audio(audio_path: Path) -> list[dict]:
    """Returns cues in the same `{start, end, text}` shape as the captions path."""
    started = time.monotonic()
    try:
        with audio_path.open("rb") as audio_file:
            transcription = await _get_client().audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
    except openai.OpenAIError as e:
        raise LLMError(_user_message(e)) from e
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
    try:
        response = await _get_client().embeddings.create(model=EMBEDDING_MODEL, input=texts)
    except openai.OpenAIError as e:
        raise LLMError(_user_message(e)) from e
    elapsed = time.monotonic() - started
    logger.info("embedded %d texts in %.1fs", len(texts), elapsed)
    if response.usage:
        _record_usage(EMBEDDING_MODEL, response.usage.prompt_tokens, 0)
    return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]


async def generate_json(
    system_prompt: str, user_prompt: str, model: str = GENERATION_MODEL
) -> dict:
    """Runs a chat completion constrained to JSON output and parses the result.
    `model` is overridden by offline eval tooling (drafting, judging), so the eval
    doesn't grade the generator with itself, and by the ingestion slip check, which
    needs a stronger model than generation does."""
    started = time.monotonic()
    try:
        response = await _get_client().chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except openai.OpenAIError as e:
        raise LLMError(_user_message(e)) from e
    elapsed = time.monotonic() - started
    usage = response.usage
    logger.info(
        "chat completion complete model=%s tokens=%s elapsed=%.1fs",
        model,
        usage.total_tokens if usage else "unknown",
        elapsed,
    )
    if usage:
        _record_usage(model, usage.prompt_tokens, usage.completion_tokens)
    choice = response.choices[0]
    if choice.message.content is None:
        raise LLMError("OpenAI returned an empty response. Try again.")
    try:
        return json.loads(choice.message.content)
    except json.JSONDecodeError as e:
        if choice.finish_reason == "length":
            raise LLMError("OpenAI's response was cut off before it finished. Try again.") from e
        raise LLMError("OpenAI returned a response that couldn't be parsed. Try again.") from e
