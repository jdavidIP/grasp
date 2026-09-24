"""Faithfulness evaluation of chat answers.

Run inside the api container:  python -m app.eval.chat [--label NAME]

Runs every golden-set question (specific, broad, and out-of-scope) through the
production chat path, then has gpt-4o (not the gpt-4o-mini answer model) judge each
answer against the sources that path returned: the chunks or segment summaries the
answer model actually saw.
"""

import argparse
import asyncio
import json
from datetime import UTC, datetime

from sqlalchemy import select

from app.db import async_session
from app.eval.faithfulness import print_usage
from app.eval.retrieval import GOLDEN_SET_PATH, RESULTS_DIR
from app.generation import llm
from app.generation.chat import answer_question
from app.models.video import Video
from app.prompts.chat_judge import (
    ANSWER_SYSTEM_PROMPT,
    DECLINE_SYSTEM_PROMPT,
    build_user_prompt,
)

CHECKS = {
    "specific": ("supported", "answers_question"),
    "broad": ("supported", "answers_question"),
    "out_of_scope": ("declines", "supported"),
}


def question_kind(entry: dict) -> str:
    if entry.get("kind") == "broad":
        return "broad"
    return "specific" if entry.get("span") else "out_of_scope"


def parse_judgment(result: dict, kind: str) -> dict | None:
    flags = (*CHECKS[kind], "speaker_slip")
    if not all(isinstance(result.get(f), bool) for f in flags):
        return None
    return {f: result[f] for f in flags} | {"reason": result.get("reason")}


def summarize(records: list[dict]) -> dict:
    """Per question kind: pass rate for each check, `faithful` (every check passed),
    the answer model's own `grounded` rate, and the share routed to the broad path.
    Check rates are over judged records; judge failures are counted as `unjudged`."""
    summary: dict = {}
    for kind, checks in CHECKS.items():
        subset = [r for r in records if r["kind"] == kind]
        if not subset:
            continue
        judged = [r["judgment"] for r in subset if r["judgment"] is not None]
        stats: dict = {"n": len(subset), "unjudged": len(subset) - len(judged)}
        for check in checks:
            stats[check] = sum(j[check] for j in judged) / len(judged) if judged else None
        stats["faithful"] = (
            sum(all(j[c] for c in checks) for j in judged) / len(judged) if judged else None
        )
        stats["speaker_slips"] = sum(j["speaker_slip"] for j in judged)
        stats["grounded"] = sum(r["grounded"] for r in subset) / len(subset)
        stats["routed_broad"] = sum(r["path"] == "broad" for r in subset) / len(subset)
        summary[kind] = stats
    return summary


async def _judge(kind: str, question: str, answer: dict) -> dict | None:
    system_prompt = DECLINE_SYSTEM_PROMPT if kind == "out_of_scope" else ANSWER_SYSTEM_PROMPT
    result = await llm.generate_json(
        system_prompt,
        build_user_prompt(question, answer["sources"], answer["answer"]),
        model=llm.EVAL_MODEL,
    )
    return parse_judgment(result, kind)


async def run(label: str | None) -> None:
    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    async with async_session() as session:
        rows = await session.execute(
            select(Video.youtube_id, Video.id).where(
                Video.youtube_id.in_({e["youtube_id"] for e in golden})
            )
        )
        video_ids = dict(rows.all())
    missing = {e["youtube_id"] for e in golden} - video_ids.keys()
    if missing:
        raise SystemExit(f"golden set references videos not in the DB: {sorted(missing)}")

    records = []
    usage: dict[str, llm.Usage] = {f"chat_{kind}": {} for kind in CHECKS} | {"judge": {}}
    # Sequential: parallel gpt-4o calls blow the org's tokens-per-minute cap.
    for entry in golden:
        kind = question_kind(entry)
        with llm.track_usage(usage[f"chat_{kind}"]):
            async with async_session() as session:
                answer = await answer_question(
                    session, video_ids[entry["youtube_id"]], entry["question"], []
                )
        with llm.track_usage(usage["judge"]):
            judgment = await _judge(kind, entry["question"], answer)
        sources = answer["sources"]
        records.append(
            {
                "id": entry["id"],
                "kind": kind,
                "question": entry["question"],
                # Only the broad path returns segment summaries, which have no chunk id.
                "path": "broad" if sources and sources[0]["chunk_id"] is None else "specific",
                "grounded": answer["grounded"],
                "answer": answer["answer"],
                "sources": [
                    {k: s[k] for k in ("segment_label", "start_time", "end_time")} for s in sources
                ],
                "judgment": judgment,
            }
        )
        print(f"{entry['id']} ({kind}): judged={judgment is not None}")

    now = datetime.now(UTC)
    output = {
        "run_at": now.isoformat(timespec="seconds"),
        "label": label,
        "judge_model": llm.EVAL_MODEL,
        "generation_model": llm.GENERATION_MODEL,
        "summary": summarize(records),
        "usage": usage,
        "items": records,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"-{label}" if label else ""
    path = RESULTS_DIR / f"chat-{now.date().isoformat()}{suffix}.json"
    path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, default=float) + "\n", encoding="utf-8"
    )
    _print_table(output["summary"])
    print_usage(usage)
    print(path)


def _print_table(summary: dict) -> None:
    columns = ("supported", "answers_question", "declines", "faithful", "grounded", "routed_broad")
    print("| kind | n | " + " | ".join(columns) + " | slips |")
    print("|---" * (len(columns) + 3) + "|")
    for kind, s in summary.items():
        cells = [f"{s[c]:.2f}" if s.get(c) is not None else "—" for c in columns]
        print(f"| {kind} | {s['n']} | " + " | ".join(cells) + f" | {s['speaker_slips']} |")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", help="suffix for the results file, e.g. 'answer-gpt-4o'")
    args = parser.parse_args()
    asyncio.run(run(args.label))
