import asyncio
import re

from app.generation import llm
from app.prompts.slip_check import SYSTEM_PROMPT, build_user_prompt

_NON_WORD_RE = re.compile(r"[^a-z0-9]+")
# ponytail: one lock per process — concurrent ingestions take turns on gpt-4o instead
# of blowing its tokens-per-minute cap together. Several API workers would need a
# shared rate limiter instead.
_slip_check_lock = asyncio.Lock()


def _normalize(text: str) -> str:
    return _NON_WORD_RE.sub(" ", text.lower()).strip()


def parse_slips(result: dict, transcript: str) -> list[dict]:
    """Keeps well-formed slips whose `said` actually occurs in the transcript, ignoring
    case and punctuation — a quote the model can't point to is an invented slip."""
    raw = result.get("slips")
    if not isinstance(raw, list):
        return []
    haystack = f" {_normalize(transcript)} "
    slips: list[dict] = []
    seen: set[str] = set()
    for slip in raw:
        if not isinstance(slip, dict):
            continue
        said, meant = slip.get("said"), slip.get("meant")
        if not isinstance(said, str) or not isinstance(meant, str):
            continue
        key = _normalize(said)
        if not key or key == _normalize(meant) or key in seen:
            continue
        if f" {key} " not in haystack:
            continue
        seen.add(key)
        slips.append({"said": said.strip(), "meant": meant.strip(), "reason": slip.get("reason")})
    return slips


def slips_in(slips: list[dict], texts: list[str]) -> list[dict]:
    """The slips whose quoted words occur in at least one of `texts`, each once — so a
    prompt only mentions slips in the passages it actually shows the model."""
    normalized = [f" {_normalize(t)} " for t in texts]
    found: list[dict] = []
    seen: set[str] = set()
    for slip in slips:
        key = _normalize(slip["said"])
        if key not in seen and any(f" {key} " in t for t in normalized):
            seen.add(key)
            found.append(slip)
    return found


def _same_slip(a: dict, b: dict) -> bool:
    """Same words flagged, same correction, allowing one quote to contain the other."""
    pairs = (
        (_normalize(a["said"]), _normalize(b["said"])),
        (_normalize(a["meant"]), _normalize(b["meant"])),
    )
    return all(x in y or y in x for x, y in pairs)


def agreed_slips(first: list[dict], second: list[dict]) -> list[dict]:
    """Slips from `first` that `second` also found with the same correction, each
    reported once. A wrong correction is rarely repeated identically by an independent
    pass, while a real slip is (docs/ARCHITECTURE.md §2)."""
    kept: list[dict] = []
    for slip in first:
        if any(_same_slip(slip, other) for other in second) and not any(
            _same_slip(slip, k) for k in kept
        ):
            kept.append(slip)
    return kept


async def detect_slips(transcript: str) -> list[dict]:
    """Speaker slips in one segment's transcript, as [{said, meant, reason}]. Two
    independent gpt-4o passes, keeping only what both agree on. One call at a time,
    across every ingestion in the process: parallel gpt-4o calls blow the org's
    tokens-per-minute cap."""
    passes = []
    for _ in range(2):
        async with _slip_check_lock:
            result = await llm.generate_json(
                SYSTEM_PROMPT, build_user_prompt(transcript), model=llm.SLIP_CHECK_MODEL
            )
        passes.append(parse_slips(result, transcript))
    return agreed_slips(*passes)
