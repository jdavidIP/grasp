"""Faithfulness evaluation of chat answers.

Run inside the api container:  python -m app.eval.chat [--label NAME]

Runs every golden-set question (specific, broad, and out-of-scope) through the
production chat path, then has gpt-4o (not the gpt-4o-mini answer model) judge each
answer against what the answer model actually saw: the reranked chunks or the segment
summaries, not the narrower list of excerpts it says it used (#47).
"""

import argparse
import asyncio
import json
from datetime import UTC, datetime

from app.db import async_session
from app.eval.faithfulness import print_usage
from app.eval.retrieval import GOLDEN_SET_PATH, RESULTS_DIR, first_hit_rank, load_eval_videos
from app.generation import llm
from app.generation.chat import answer_question, with_slip_notes
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
    the final `grounded` rate, the share routed to the broad path, sources per answer
    and how often the model gave no used-excerpts list (`fallbacks`). `flipped` counts
    answers the model called grounded that used no excerpt, so they show as not
    covered; for answerable kinds, `false_alarms` are the flipped ones the judge found
    supported. For specific questions, `span_kept` is the share of those whose
    retrieved excerpts overlapped the golden span where the used excerpts still do.
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
        stats["mean_sources"] = sum(r["n_sources"] for r in subset) / len(subset)
        stats["fallbacks"] = sum(r["sources_fallback"] for r in subset)
        flipped = [r for r in subset if r["model_grounded"] and not r["grounded"]]
        stats["flipped"] = len(flipped)
        if kind != "out_of_scope":
            stats["false_alarms"] = sum(
                r["judgment"] is not None and r["judgment"]["supported"] for r in flipped
            )
        if kind == "specific":
            retrieved = [r for r in subset if r["span_in_context"]]
            stats["span_kept"] = (
                sum(r["span_in_sources"] for r in retrieved) / len(retrieved) if retrieved else None
            )
        summary[kind] = stats
    return summary


def _overlaps(sources: list[dict], span: tuple[float, float]) -> bool:
    return first_hit_rank([(s["start_time"], s["end_time"]) for s in sources], span) is not None


async def _judge(kind: str, question: str, answer: dict) -> dict | None:
    system_prompt = DECLINE_SYSTEM_PROMPT if kind == "out_of_scope" else ANSWER_SYSTEM_PROMPT
    result = await llm.generate_json(
        system_prompt,
        # The judge must see what the viewer reads: the answer plus its slip notes.
        build_user_prompt(
            question, answer["context"], with_slip_notes(answer["answer"], answer["slips"])
        ),
        model=llm.EVAL_MODEL,
    )
    return parse_judgment(result, kind)


async def run(label: str | None) -> None:
    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    videos = await load_eval_videos({e["youtube_id"] for e in golden})
    video_ids = {y: v.id for y, v in videos.items()}

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
        span = tuple(entry["span"]) if kind == "specific" else None
        records.append(
            {
                "id": entry["id"],
                "kind": kind,
                "question": entry["question"],
                "path": answer["path"],
                "grounded": answer["grounded"],
                "model_grounded": answer["model_grounded"],
                "n_sources": len(sources),
                "sources_fallback": answer["sources_fallback"],
                "span_in_context": _overlaps(answer["context"], span) if span else None,
                "span_in_sources": _overlaps(sources, span) if span else None,
                "answer": with_slip_notes(answer["answer"], answer["slips"]),
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
    columns = (
        "supported",
        "answers_question",
        "declines",
        "faithful",
        "grounded",
        "routed_broad",
        "mean_sources",
        "span_kept",
        "flipped",
        "false_alarms",
        "fallbacks",
    )
    print("| kind | n | " + " | ".join(columns) + " | slips |")
    print("|---" * (len(columns) + 3) + "|")
    for kind, s in summary.items():
        cells = [_cell(s.get(c)) for c in columns]
        print(f"| {kind} | {s['n']} | " + " | ".join(cells) + f" | {s['speaker_slips']} |")


def _cell(value: float | None) -> str:
    if value is None:
        return "—"
    return str(value) if isinstance(value, int) else f"{value:.2f}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", help="suffix for the results file, e.g. 'answer-gpt-4o'")
    args = parser.parse_args()
    asyncio.run(run(args.label))
