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
| vector only | 0.73 | 0.92 | 0.92 | 0.82 |
| hybrid (vector + keyword, RRF) | 0.81 | 0.92 | 0.96 | 0.87 |
| **hybrid + LLM rerank** (production) | **0.88** | **0.96** | **0.96** | **0.92** |

**Out-of-scope questions correctly declined: 6/6.**

The eval paid for itself on its first run. Keyword search used `plainto_tsquery`, which requires *every* term in the question to appear in a chunk. It matched nothing on 19 of 20 questions, so "hybrid" search had silently been pure vector search. Switching to any-term matching raised hybrid + rerank hit@1 from **0.81 to 0.88** and MRR from **0.86 to 0.92**. A lecture question about the Marshall Plan, which no strategy had retrieved at any rank, went to rank 1: an exact name the embedding had flattened, which is the case hybrid search exists for. ([before](api/eval/results/retrieval-2026-09-19.json) / [after](api/eval/results/retrieval-2026-09-19-keyword-or.json))

### Generation faithfulness

gpt-4o judges every generated flashcard and quiz question against the raw transcript of the segment it cites. It uses a different model from the gpt-4o-mini generator, so the generator isn't grading itself. Rates are reported before the pipeline's own validation pass (raw) and after it (what users see).

| | raw | shipped to user |
|---|---|---|
| flashcards: faithful | 0.86 (n=36) | 0.81 (n=27) |
| quiz questions: faithful | 0.76 (n=34) | 0.80 (n=30) |
| quiz questions: answer key correct | 0.76 | 0.80 |

With about 30 items per group, differences under about 0.1 are within run-to-run noise. The judge's per-item reasoning is in [the results file](api/eval/results/faithfulness-2026-09-19.json). What it shows:

- **The flashcard grounding validator is counterproductive right now.** All 7 cards it rejected were judged faithful. It only sees each segment's summary and two excerpts, so it can't verify cards grounded elsewhere in the segment ([#15](https://github.com/jdavidIP/grasp/issues/15)).
- **Quiz answer keys are the weakest link.** About 1 in 5 shipped questions has a "wrong" option that is actually true, mostly in multi-select ([#16](https://github.com/jdavidIP/grasp/issues/16)). Grading is deterministic, so a bad key marks a correct answer wrong.

### Known limitations

- **Segmentation of auto-captioned videos** ([#15](https://github.com/jdavidIP/grasp/issues/15)). Auto captions have no punctuation, which defeats sentence grouping: the 3-hour podcast became 4 topics and the tutorial became 1. That thins out the topic picker and the context available for generation. Segmentation is reviewed by hand and not scored automatically.
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
