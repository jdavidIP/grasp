import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import openai
import pytest

from app.generation import llm


def _status_error(cls: type[openai.APIStatusError], status: int) -> openai.APIStatusError:
    request = httpx.Request("POST", "https://api.openai.com/v1/x")
    response = httpx.Response(status, request=request, json={"error": {"message": "x"}})
    return cls("x", response=response, body=None)


def _connection_error(cls: type[openai.APIConnectionError]) -> openai.APIConnectionError:
    request = httpx.Request("POST", "https://api.openai.com/v1/x")
    return cls(request=request)


@pytest.mark.parametrize(
    "error, expected_substring",
    [
        (_status_error(openai.AuthenticationError, 401), "API key"),
        (_status_error(openai.RateLimitError, 429), "rate limit"),
        (_connection_error(openai.APITimeoutError), "didn't respond in time"),
        (_connection_error(openai.APIConnectionError), "reach OpenAI"),
        (_status_error(openai.InternalServerError, 500), "temporarily unavailable"),
        (openai.OpenAIError(), "request failed"),
    ],
)
def test_user_message_translates_by_cause(error, expected_substring):
    assert expected_substring in llm._user_message(error)


def test_user_message_checks_auth_before_the_general_status_error():
    # AuthenticationError IS an APIStatusError — the specific message must win.
    assert llm._user_message(_status_error(openai.AuthenticationError, 401)) != llm._user_message(
        _status_error(openai.InternalServerError, 500)
    )


async def test_generate_json_wraps_openai_error_as_llm_error(monkeypatch):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        side_effect=_status_error(openai.RateLimitError, 429)
    )
    monkeypatch.setattr(llm, "_get_client", lambda: client)

    with pytest.raises(llm.LLMError, match="rate limit") as exc_info:
        await llm.generate_json("system", "user")
    assert isinstance(exc_info.value.__cause__, openai.RateLimitError)


async def test_embed_texts_wraps_openai_error_as_llm_error(monkeypatch):
    client = MagicMock()
    client.embeddings.create = AsyncMock(side_effect=_status_error(openai.AuthenticationError, 401))
    monkeypatch.setattr(llm, "_get_client", lambda: client)

    with pytest.raises(llm.LLMError, match="API key"):
        await llm.embed_texts(["hello"])


async def test_transcribe_audio_wraps_openai_error_as_llm_error(monkeypatch, tmp_path):
    client = MagicMock()
    client.audio.transcriptions.create = AsyncMock(
        side_effect=_connection_error(openai.APIConnectionError)
    )
    monkeypatch.setattr(llm, "_get_client", lambda: client)
    audio_path = tmp_path / "audio.m4a"
    audio_path.write_bytes(b"fake")

    with pytest.raises(llm.LLMError, match="reach OpenAI"):
        await llm.transcribe_audio(audio_path)


def _completion(content: str | None, finish_reason: str = "stop") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish_reason)
        ],
        usage=SimpleNamespace(total_tokens=10, prompt_tokens=7, completion_tokens=3),
    )


async def test_generate_json_untouched_on_success(monkeypatch):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_completion('{"ok": true}'))
    monkeypatch.setattr(llm, "_get_client", lambda: client)

    assert await llm.generate_json("system", "user") == {"ok": True}


async def test_track_usage_totals_per_model_including_concurrent_tasks(monkeypatch):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_completion('{"ok": true}'))
    client.embeddings.create = AsyncMock(
        return_value=SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[0.1])],
            usage=SimpleNamespace(prompt_tokens=5),
        )
    )
    monkeypatch.setattr(llm, "_get_client", lambda: client)

    await llm.generate_json("system", "user")  # outside any block: not recorded
    with llm.track_usage() as usage:
        await asyncio.gather(
            llm.generate_json("system", "user"),
            llm.generate_json("system", "user", model=llm.EVAL_MODEL),
            llm.generate_json("system", "user", model=llm.EVAL_MODEL),
        )
        await llm.embed_texts(["hello"])

    assert usage == {
        llm.GENERATION_MODEL: {"calls": 1, "prompt_tokens": 7, "completion_tokens": 3},
        llm.EVAL_MODEL: {"calls": 2, "prompt_tokens": 14, "completion_tokens": 6},
        llm.EMBEDDING_MODEL: {"calls": 1, "prompt_tokens": 5, "completion_tokens": 0},
    }

    with llm.track_usage(usage):
        await llm.generate_json("system", "user")
    assert usage[llm.GENERATION_MODEL] == {"calls": 2, "prompt_tokens": 14, "completion_tokens": 6}


async def test_generate_json_raises_when_content_is_none(monkeypatch):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_completion(None))
    monkeypatch.setattr(llm, "_get_client", lambda: client)

    with pytest.raises(llm.LLMError, match="empty response"):
        await llm.generate_json("system", "user")


async def test_generate_json_raises_specific_message_when_truncated(monkeypatch):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        return_value=_completion('{"partial":', finish_reason="length")
    )
    monkeypatch.setattr(llm, "_get_client", lambda: client)

    with pytest.raises(llm.LLMError, match="cut off"):
        await llm.generate_json("system", "user")


async def test_generate_json_raises_when_content_is_invalid_json(monkeypatch):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_completion("not json"))
    monkeypatch.setattr(llm, "_get_client", lambda: client)

    with pytest.raises(llm.LLMError, match="couldn't be parsed"):
        await llm.generate_json("system", "user")
