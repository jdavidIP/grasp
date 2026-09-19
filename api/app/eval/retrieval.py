"""Retrieval evaluation against the golden set (`api/eval/golden_set.json`).

Run inside the api container:  python -m app.eval.retrieval [--label NAME]

Golden entries point at a time span in the video, not at chunk ids — chunk ids change
on every reprocess, and span-based scoring lets chunking parameters be compared on the
same golden set. See docs/ARCHITECTURE.md §6 for the metric definitions.
"""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.db import async_session
from app.generation import llm
from app.generation.chat import answer_question
from app.ingestion.chunking import CHUNK_OVERLAP_RATIO, CHUNK_TARGET_TOKENS
from app.models.chunk import TranscriptChunk
from app.models.video import Video
from app.retrieval.rerank import RERANK_KEEP, rerank
from app.retrieval.search import RRF_K, VECTOR_SEARCH_K, hybrid_search, vector_search

EVAL_DIR = Path(__file__).resolve().parents[2] / "eval"
GOLDEN_SET_PATH = EVAL_DIR / "golden_set.json"
RESULTS_DIR = EVAL_DIR / "results"

KS = (1, 3, 5, 8)
STRATEGIES = ("vector", "hybrid", "hybrid_rerank")

Span = tuple[float, float]


def first_hit_rank(retrieved: list[Span], span: Span) -> int | None:
    """1-based rank of the first retrieved range overlapping the span, else None."""
    for rank, (start, end) in enumerate(retrieved, start=1):
        if start < span[1] and end > span[0]:
            return rank
    return None


def span_coverage(retrieved: list[Span], span: Span) -> float:
    """Fraction of the span's duration covered by the union of the retrieved ranges."""
    pieces = sorted(
        (max(start, span[0]), min(end, span[1]))
        for start, end in retrieved
        if start < span[1] and end > span[0]
    )
    covered, cursor = 0.0, span[0]
    for start, end in pieces:
        start = max(start, cursor)
        if end > start:
            covered += end - start
            cursor = end
    length = span[1] - span[0]
    return covered / length if length > 0 else 0.0


def summarize(results: list[tuple[list[Span], Span]], ks: tuple[int, ...] = KS) -> dict:
    """hit_rate@k, recall@k (mean span coverage), and MRR over (retrieved, span) pairs.
    k values beyond what a strategy returns are omitted rather than padded."""
    n = len(results)
    if n == 0:
        return {}
    max_returned = max(len(retrieved) for retrieved, _ in results)
    summary: dict[str, float] = {}
    for k in ks:
        if k > max_returned:
            continue
        hits = 0
        for retrieved, span in results:
            rank = first_hit_rank(retrieved[:k], span)
            hits += rank is not None
        summary[f"hit_rate@{k}"] = hits / n
        summary[f"recall@{k}"] = sum(span_coverage(r[:k], s) for r, s in results) / n
    reciprocal_ranks = [1 / rank if (rank := first_hit_rank(r, s)) else 0.0 for r, s in results]
    summary["mrr"] = sum(reciprocal_ranks) / n
    return summary


async def _retrieve(
    strategy: str, video_id, question: str, embedding: list[float]
) -> list[TranscriptChunk]:
    async with async_session() as session:
        if strategy == "vector":
            return await vector_search(session, video_id, embedding)
        candidates = await hybrid_search(session, video_id, question, embedding)
        if strategy == "hybrid":
            return candidates
        return await rerank(question, candidates)


async def _decline(video_id, question: str) -> dict:
    async with async_session() as session:
        return await answer_question(session, video_id, question, [])


async def run(label: str | None) -> Path:
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

    in_scope = [e for e in golden if e.get("span")]
    out_of_scope = [e for e in golden if not e.get("span")]
    embeddings = await llm.embed_texts([e["question"] for e in in_scope])

    per_question = []
    by_strategy: dict[str, list[tuple[list[Span], Span]]] = {s: [] for s in STRATEGIES}
    for entry, embedding in zip(in_scope, embeddings, strict=True):
        span = (float(entry["span"][0]), float(entry["span"][1]))
        record = {"id": entry["id"], "question": entry["question"], "span": list(span)}
        for strategy in STRATEGIES:
            chunks = await _retrieve(
                strategy, video_ids[entry["youtube_id"]], entry["question"], embedding
            )
            retrieved = [(float(c.start_time), float(c.end_time)) for c in chunks]
            by_strategy[strategy].append((retrieved, span))
            record[strategy] = {
                "first_hit_rank": first_hit_rank(retrieved, span),
                "retrieved": [list(r) for r in retrieved],
            }
        per_question.append(record)

    declines = []
    for entry in out_of_scope:
        answer = await _decline(video_ids[entry["youtube_id"]], entry["question"])
        declines.append(
            {
                "id": entry["id"],
                "question": entry["question"],
                "declined": not answer["grounded"],
                "answer": answer["answer"],
            }
        )

    now = datetime.now(UTC)
    output = {
        "run_at": now.isoformat(timespec="seconds"),
        "label": label,
        "config": {
            "chunk_target_tokens": CHUNK_TARGET_TOKENS,
            "chunk_overlap_ratio": CHUNK_OVERLAP_RATIO,
            "vector_search_k": VECTOR_SEARCH_K,
            "rrf_k": RRF_K,
            "rerank_keep": RERANK_KEEP,
        },
        "counts": {"in_scope": len(in_scope), "out_of_scope": len(out_of_scope)},
        "summary": {s: summarize(by_strategy[s]) for s in STRATEGIES},
        "out_of_scope_decline_rate": (
            sum(d["declined"] for d in declines) / len(declines) if declines else None
        ),
        "questions": per_question,
        "out_of_scope": declines,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"-{label}" if label else ""
    path = RESULTS_DIR / f"retrieval-{now.date().isoformat()}{suffix}.json"
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    _print_table(output)
    return path


def _print_table(output: dict) -> None:
    metrics = [m for m in output["summary"]["vector"] if m != "mrr"] + ["mrr"]
    print("| strategy | " + " | ".join(metrics) + " |")
    print("|---" * (len(metrics) + 1) + "|")
    for strategy, summary in output["summary"].items():
        cells = [f"{summary[m]:.2f}" if m in summary else "—" for m in metrics]
        print(f"| {strategy} | " + " | ".join(cells) + " |")
    rate = output["out_of_scope_decline_rate"]
    if rate is not None:
        print(f"\nout-of-scope decline rate: {rate:.2f} ({output['counts']['out_of_scope']} qs)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", help="suffix for the results file, e.g. 'chunk300'")
    args = parser.parse_args()
    print(asyncio.run(run(args.label)))
