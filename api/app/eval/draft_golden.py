"""Drafts golden-set candidates for human review.

Run inside the api container:
    python -m app.eval.draft_golden [--per-video N] [--out-of-scope M] YOUTUBE_ID ...

Writes `api/eval/golden_set.draft.json`. Review it by hand — fix or delete weak
questions, tighten spans to where the answer is actually said — then save the result
as `api/eval/golden_set.json`. The retrieval eval only reads the reviewed file.
"""

import argparse
import asyncio
import json

from sqlalchemy import select

from app.db import async_session
from app.eval.retrieval import EVAL_DIR
from app.generation import llm
from app.models.video import Video
from app.prompts.golden_draft import (
    OUT_OF_SCOPE_SYSTEM_PROMPT,
    QUESTION_SYSTEM_PROMPT,
    build_out_of_scope_user_prompt,
    build_question_user_prompt,
)

DRAFT_PATH = EVAL_DIR / "golden_set.draft.json"
WINDOW_SECONDS = 40.0
OVERSAMPLE = 2


def spread_pick(items: list, count: int) -> list:
    """Up to `count` items chosen evenly across the list, preserving order."""
    if len(items) <= count:
        return items
    return [items[int(i * len(items) / count)] for i in range(count)]


def sample_windows(cues: list[dict], count: int) -> list[list[dict]]:
    """`count` runs of consecutive cues, each ~WINDOW_SECONDS long, spread evenly
    across the transcript so the golden set covers the whole video, not its intro."""
    if not cues or count <= 0:
        return []
    windows = []
    for i in range(count):
        start_index = int(len(cues) * (i + 0.5) / count)
        window, j = [], start_index
        while j < len(cues) and (
            not window or cues[j - 1]["end"] - window[0]["start"] < WINDOW_SECONDS
        ):
            window.append(cues[j])
            j += 1
        windows.append(window)
    return windows


async def _draft_question(
    video: Video, topics: list[tuple[str, str]], window: list[dict]
) -> dict | None:
    excerpt = " ".join(cue["text"] for cue in window)
    result = await llm.generate_json(
        QUESTION_SYSTEM_PROMPT,
        build_question_user_prompt(video.title, topics, excerpt),
        model=llm.EVAL_MODEL,
    )
    question = result.get("question")
    if not isinstance(question, str) or not question.strip():
        return None
    return {
        "youtube_id": video.youtube_id,
        "question": question.strip(),
        "answer": result.get("answer"),
        "note": result.get("note"),
        "span": [round(window[0]["start"], 1), round(window[-1]["end"], 1)],
        "excerpt": excerpt,
    }


async def _draft_out_of_scope(video: Video, count: int) -> list[dict]:
    topics = [(s.label, s.summary) for s in video.segments]
    result = await llm.generate_json(
        OUT_OF_SCOPE_SYSTEM_PROMPT,
        build_out_of_scope_user_prompt(video.title, topics, count),
        model=llm.EVAL_MODEL,
    )
    questions = result.get("questions")
    if not isinstance(questions, list):
        return []
    return [
        {"youtube_id": video.youtube_id, "question": q.strip(), "span": None}
        for q in questions[:count]
        if isinstance(q, str) and q.strip()
    ]


async def draft(youtube_ids: list[str], per_video: int, out_of_scope: int) -> None:
    async with async_session() as session:
        result = await session.execute(select(Video).where(Video.youtube_id.in_(youtube_ids)))
        videos = {v.youtube_id: v for v in result.scalars()}
    missing = set(youtube_ids) - videos.keys()
    if missing:
        raise SystemExit(f"not in the DB: {sorted(missing)}")

    entries = []
    for youtube_id in youtube_ids:
        video = videos[youtube_id]
        topics = [(s.label, s.summary) for s in video.segments]
        # Oversample: the prompt nulls out off-topic windows (logistics, small talk).
        windows = sample_windows(video.transcript or [], per_video * OVERSAMPLE)
        # Sequential, not gathered: parallel gpt-4o calls blow the org's tokens-per-minute cap.
        drafted = [await _draft_question(video, topics, w) for w in windows]
        entries += spread_pick([d for d in drafted if d is not None], per_video)
        entries += await _draft_out_of_scope(video, out_of_scope)

    for i, entry in enumerate(entries, start=1):
        entry["id"] = f"{entry['youtube_id']}-{i:02d}"
    ordered = [{"id": e.pop("id"), **e} for e in entries]
    DRAFT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DRAFT_PATH.write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"wrote {len(ordered)} candidates to {DRAFT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("youtube_ids", nargs="+")
    parser.add_argument("--per-video", type=int, default=10)
    parser.add_argument("--out-of-scope", type=int, default=2)
    args = parser.parse_args()
    asyncio.run(draft(args.youtube_ids, args.per_video, args.out_of_scope))
