"""Faithfulness evaluation of generated flashcards and quiz questions.

Run inside the api container:  python -m app.eval.faithfulness [--label NAME]

Generates a fresh deck and quiz per golden-set video from fixed configs, then has
gpt-4o (not the gpt-4o-mini generator) judge every candidate against the transcript
of the segment it cites. Candidates are judged once and tagged with whether they
survived the pipeline's own validation, so the report shows both what the model
raw-produced and what a user would actually see — i.e. what validation buys.
"""

import argparse
import asyncio
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.db import async_session
from app.eval.retrieval import GOLDEN_SET_PATH, RESULTS_DIR
from app.generation import llm
from app.generation.common import segment_text
from app.generation.flashcards import generate_flashcards
from app.generation.quizzes import generate_quiz
from app.models.video import Video
from app.prompts.faithfulness_judge import (
    FLASHCARD_SYSTEM_PROMPT,
    QUIZ_SYSTEM_PROMPT,
    build_flashcard_user_prompt,
    build_quiz_user_prompt,
)

FLASHCARD_CONFIG = {"count": 10, "scope": "whole_video", "difficulty": "medium", "style": "mixed"}
QUIZ_CONFIG = {
    "count": 10,
    "scope": "whole_video",
    "question_types": ["multiple_choice", "multi_select", "true_false"],
    "options_per_question": 4,
    "difficulty": "medium",
}
CHECKS = {
    "flashcards": ("supported", "answerable"),
    "quizzes": ("supported", "answerable", "key_correct"),
}


def summarize(records: list[dict]) -> dict:
    """Per kind, pass rates for every check at each pipeline stage: `raw` (all
    candidates), `rejected` (what the LLM validation pass threw out), and `kept` (what
    a user sees). `faithful` means every check for that kind passed. Rates are over
    judged items; items the judge skipped are counted separately."""
    summary: dict = {}
    for kind, checks in CHECKS.items():
        kind_records = [r for r in records if r["kind"] == kind]
        if not kind_records:
            continue
        summary[kind] = {}
        for stage, subset in (
            ("raw", kind_records),
            ("rejected", [r for r in kind_records if not r["validated"]]),
            ("kept", [r for r in kind_records if r["kept"]]),
        ):
            judged = [r["judgment"] for r in subset if r["judgment"] is not None]
            stats: dict = {"n": len(subset), "unjudged": len(subset) - len(judged)}
            for check in (*checks, "faithful"):
                if check == "faithful":
                    passed = sum(all(j[c] for c in checks) for j in judged)
                else:
                    passed = sum(j[check] for j in judged)
                stats[check] = passed / len(judged) if judged else None
            stats["speaker_slips"] = sum(j["speaker_slip"] for j in judged)
            summary[kind][stage] = stats
    return summary


def _parse_judgments(result: dict, count: int, checks: tuple[str, ...]) -> list[dict | None]:
    judgments: list[dict | None] = [None] * count
    raw = result.get("judgments")
    if not isinstance(raw, list):
        return judgments
    for j in raw:
        if not isinstance(j, dict):
            continue
        index = j.get("index")
        flags = (*checks, "speaker_slip")
        if not isinstance(index, int) or not 0 <= index < count:
            continue
        if not all(isinstance(j.get(f), bool) for f in flags):
            continue
        judgments[index] = {f: j[f] for f in flags} | {"reason": j.get("reason")}
    return judgments


async def _judge(kind: str, transcript: str, items: list[dict]) -> list[dict | None]:
    if kind == "flashcards":
        prompts = (FLASHCARD_SYSTEM_PROMPT, build_flashcard_user_prompt(transcript, items))
    else:
        prompts = (QUIZ_SYSTEM_PROMPT, build_quiz_user_prompt(transcript, items))
    result = await llm.generate_json(*prompts, model=llm.EVAL_MODEL)
    return _parse_judgments(result, len(items), CHECKS[kind])


async def _generate(kind: str, video_id: uuid.UUID) -> dict:
    trace: dict = {}
    async with async_session() as session:
        if kind == "flashcards":
            await generate_flashcards(
                session, video_id, segment_ids=[], trace=trace, **FLASHCARD_CONFIG
            )
        else:
            await generate_quiz(session, video_id, segment_ids=[], trace=trace, **QUIZ_CONFIG)
    return trace


def _item_view(kind: str, item: dict) -> dict:
    if kind == "flashcards":
        return {"front": item["front"], "back": item["back"], "note": item.get("note")}
    return {
        "question_type": item["question_type"],
        "prompt": item["prompt"],
        "options": item["options"],
        "explanation": item["explanation"],
    }


async def run(label: str | None) -> None:
    youtube_ids = sorted({e["youtube_id"] for e in json.loads(GOLDEN_SET_PATH.read_text("utf-8"))})
    async with async_session() as session:
        result = await session.execute(select(Video).where(Video.youtube_id.in_(youtube_ids)))
        videos = list(result.scalars())

    records = []
    usage: dict[str, llm.Usage] = {kind: {} for kind in CHECKS} | {"judge": {}}
    for video in videos:
        for kind in CHECKS:
            with llm.track_usage(usage[kind]):
                trace = await _generate(kind, video.id)
            candidates, segments = trace.get("candidates", []), trace.get("segments", [])
            validated_ids = {id(v) for v in trace.get("validated", [])}
            kept_ids = {id(k) for k in trace.get("kept", [])}
            by_topic: dict[int, list[dict]] = {}
            for candidate in candidates:
                by_topic.setdefault(candidate["topic_index"], []).append(candidate)
            # Sequential: parallel gpt-4o calls blow the org's tokens-per-minute cap.
            for topic_index, items in by_topic.items():
                segment = segments[topic_index]
                transcript = segment_text(video.transcript or [], segment)
                with llm.track_usage(usage["judge"]):
                    judgments = await _judge(kind, transcript, items)
                for item, judgment in zip(items, judgments, strict=True):
                    records.append(
                        {
                            "youtube_id": video.youtube_id,
                            "kind": kind,
                            "segment": segment.label,
                            "validated": id(item) in validated_ids,
                            "kept": id(item) in kept_ids,
                            **_item_view(kind, item),
                            "judgment": judgment,
                        }
                    )
            print(
                f"{video.youtube_id} {kind}: {len(candidates)} candidates, "
                f"{len(validated_ids)} validated, {len(kept_ids)} kept"
            )

    now = datetime.now(UTC)
    output = {
        "run_at": now.isoformat(timespec="seconds"),
        "label": label,
        "judge_model": llm.EVAL_MODEL,
        "generation_model": llm.GENERATION_MODEL,
        "config": {"flashcards": FLASHCARD_CONFIG, "quizzes": QUIZ_CONFIG},
        "videos": youtube_ids,
        "summary": summarize(records),
        "usage": usage,
        "items": records,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"-{label}" if label else ""
    path = RESULTS_DIR / f"faithfulness-{now.date().isoformat()}{suffix}.json"
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _print_table(output["summary"])
    print_usage(usage)
    print(path)


def print_usage(usage: dict[str, llm.Usage]) -> None:
    print("\n| feature | model | calls | prompt tokens | completion tokens |")
    print("|---|---|---|---|---|")
    for feature, by_model in usage.items():
        for model, u in by_model.items():
            print(
                f"| {feature} | {model} | {u['calls']} | "
                f"{u['prompt_tokens']:,} | {u['completion_tokens']:,} |"
            )


def _print_table(summary: dict) -> None:
    print("| kind | stage | n | supported | answerable | key_correct | faithful | slips |")
    print("|---|---|---|---|---|---|---|---|")
    for kind, stages in summary.items():
        for stage, s in stages.items():
            cells = [
                f"{s[c]:.2f}" if s.get(c) is not None else "—"
                for c in ("supported", "answerable", "key_correct", "faithful")
            ]
            print(
                f"| {kind} | {stage} | {s['n']} | "
                + " | ".join(cells)
                + f" | {s['speaker_slips']} |"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", help="suffix for the results file, e.g. 'prompt-v2'")
    args = parser.parse_args()
    asyncio.run(run(args.label))
