# Grasp

A study companion built on a RAG pipeline over YouTube transcripts. Add a video to your library, then chat with it (grounded answers with clickable timestamps), generate flashcard decks, or generate quizzes. Every answer, card, and question traces back to a moment in the video.

The point of the project is **retrieval and generation quality**, and it is measured rather than asserted. See [Evaluation](#evaluation).

## Running it

Requires Docker and an OpenAI API key.

```bash
export OPENAI_API_KEY=sk-...
docker compose up --build
docker compose exec api alembic upgrade head
```

The web app runs at http://localhost:5173 and the API at http://localhost:8000/api.

## Evaluation

Two offline evals, run inside the `api` container. Results are committed as dated JSON under [`api/eval/results/`](api/eval/results/). Methodology and trade-offs are in [`docs/ARCHITECTURE.md` §6](docs/ARCHITECTURE.md#6-evaluation).

```bash
docker compose exec api python -m app.eval.retrieval      # retrieval metrics
docker compose exec api python -m app.eval.faithfulness   # LLM-judged generation quality
```

The eval set covers three deliberately different videos: a 56-minute university lecture, a 3-hour podcast, and a 10-minute programming tutorial. The golden set has 26 hand-reviewed questions, each with the time span where the video answers it, plus 6 adjacent questions the video *doesn't* answer.

### Retrieval

A retrieved chunk counts as a hit if it overlaps the golden time span. Production retrieves 8 candidates by hybrid search, then reranks down to 5.

| strategy | hit@1 | hit@3 | hit@5 | MRR |
|---|---|---|---|---|
| vector only | 0.81 | 0.88 | 0.92 | 0.86 |
| hybrid (vector + keyword, RRF) | 0.81 | 0.88 | 0.92 | 0.86 |
| **hybrid + LLM rerank** (production) | **0.81** | **0.96** | **0.96** | **0.88** |

**Out-of-scope questions correctly declined: 6/6.**

The eval paid for itself on its first run. Keyword search used `plainto_tsquery`, which requires *every* term in the question to appear in a chunk. It matched nothing on 24 of the 26 questions, so "hybrid" search had silently been pure vector search. Switching to any-term matching raised hybrid + rerank hit@1 from **0.81 to 0.88** and MRR from **0.86 to 0.92**. A lecture question about the Marshall Plan, which no strategy had retrieved at any rank, went to rank 1: an exact name the embedding had flattened, which is the case hybrid search exists for. ([before](api/eval/results/retrieval-2026-09-19.json) / [after](api/eval/results/retrieval-2026-09-19-keyword-or.json))

The segmentation fix ([#15](https://github.com/jdavidIP/grasp/issues/15)) then cost some of that at rank 1. Chunks never cross topic boundaries, so better topics moved every chunk boundary, and production hit@1 went from 0.88 to 0.81 (identical across two runs) while hit@3 held at 0.96. I accepted the trade: every answer still reaches the chat model among the 5 reranked chunks, and the generation metrics below improved. ([results](api/eval/results/retrieval-2026-09-19-segmentation.json))

### Generation faithfulness

gpt-4o judges every generated flashcard and quiz question against the raw transcript of the segment it cites. It uses a different model from the gpt-4o-mini generator, so the generator isn't grading itself. Rates are reported before the pipeline's own validation pass (raw) and after it (what users see).

| | raw | shipped to user |
|---|---|---|
| flashcards: faithful | 0.81 (n=36) | 0.86 (n=28) |
| quiz questions: faithful | 0.85 (n=34) | 0.86 (n=29) |
| quiz questions: answer key correct | 0.85 | 0.86 |

With about 30 items per group, differences under about 0.1 are within run-to-run noise. The judge's per-item reasoning is in [the results file](api/eval/results/faithfulness-2026-09-19-segmentation.json). What it shows:

- **Fixing segmentation turned the flashcard validator from harmful to useful.** At the [first baseline](api/eval/results/faithfulness-2026-09-19.json), all 7 cards the validator rejected were judged faithful, and shipped cards scored *below* raw output (0.81 vs 0.86). The validator only sees each topic's summary plus two excerpts, and the podcast's 4 hour-long "topics" left it almost nothing to check against. With 20 real topics, shipped cards now score above raw (0.86 vs 0.81). The validator still rejects some good cards (3 of the 5 it rejected were faithful, down from 7 of 7), so it is far from precise, but on balance it now helps. The tutorial deck also went from 7 to 10 of the 10 cards requested.
- **Quiz answer keys are the weakest link.** About 1 in 7 shipped questions (1 in 5 at baseline) has a wrong or unsupported answer key. At baseline these were mostly multi-select questions with a "wrong" option that is actually true; in the latest run 3 of the 4 are true/false statements the transcript doesn't support ([#16](https://github.com/jdavidIP/grasp/issues/16)). Grading is deterministic, so a bad key marks a correct answer wrong.

### Known limitations

- **Segmentation is reviewed by hand, not scored.** Reviewing the eval videos is how the auto-caption bug was found (the 3-hour podcast had become 4 topics; it's now 20). Whole-video generation still gives every topic the same 2 excerpts, so the podcast's longest topic (28 minutes) is only ~15% represented. This is a known limit, deferred until an eval shows it hurts ([#15](https://github.com/jdavidIP/grasp/issues/15)).
- **Small eval set.** 26 retrieval questions and about 30 judged items per group give directional numbers, not precise ones. At about 500 tokens per chunk, the tutorial has only 6 chunks, so @5 and @8 saturate for short videos. hit@1 and MRR are the metrics that separate strategies.
- **Broad questions are untested.** Every golden question is specific. "Summarize this video"-style questions take a separate chat path that the eval doesn't measure yet.
- **Chunk size is untuned.** Both lecture questions missed at baseline had their answer diluted inside a ~500-token chunk mostly about something else ([#17](https://github.com/jdavidIP/grasp/issues/17)).
- **Speaker slips reach learners.** When a speaker misspeaks (the tutorial says lists use "angle brackets"), generated cards repeat it as fact ([#18](https://github.com/jdavidIP/grasp/issues/18)).
- **The judge is an LLM.** It follows a strict rubric and writes its reasoning before each verdict, but it still makes mistakes. For example, it treated a caption mishearing ("accept" for `except`) as a speaker slip.
- **Test isolation** ([#14](https://github.com/jdavidIP/grasp/issues/14)). The test suite currently writes to the dev database.

## Docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): ingestion, segmentation, retrieval, generation, and evaluation.
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md): schema and pgvector setup.
- [`docs/API.md`](docs/API.md): endpoint contracts.
- [`docs/ROADMAP.md`](docs/ROADMAP.md): build order.
