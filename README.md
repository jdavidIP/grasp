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

| | Phase 7 baseline (1 run) | now (2 runs) |
|---|---|---|
| quiz questions: answer key correct | 0.80 | 0.93, 0.93 |
| quiz questions shipped, of 30 requested | 30 | 30, 30 |
| flashcards: faithful | 0.81 | 0.83, 0.90 |
| flashcards shipped, of 30 requested | 27 | 30, 30 |

Single runs on about 30 items are noisy: *identical* code scored 0.71 and 0.87 on quiz key correctness. So every change below was judged on at least two runs, and the per-run results are all committed under [`api/eval/results/`](api/eval/results/). The judge's per-item reasoning is in each results file. What it shows:

- **The validators were checking against the wrong context, and one run made that look fixed.** After the segmentation fix ([#15](https://github.com/jdavidIP/grasp/issues/15)) a single run showed shipped flashcards scoring above raw output, so the flashcard validator looked net-useful. Two more runs said otherwise: it rejected 11 and 14 cards, of which 11 and 12 were faithful, and shipped decks of 23 and 21 of 30. The cause, for both flashcards and quizzes, was that each validator checked items against the same summary-plus-two-excerpts context the generator had seen. It couldn't verify items grounded elsewhere in a topic (so it rejected good ones), and it couldn't tell a fact stated in the video from one the generator filled in from general knowledge (so it kept bad ones).
- **Fix ([#16](https://github.com/jdavidIP/grasp/issues/16)): validate each item against the full transcript of the segment it cites,** one call per cited segment, in parallel. By my token estimate it costs about the same, because only cited segments are sent (I haven't measured it: [#21](https://github.com/jdavidIP/grasp/issues/21)). Wrongly rejected cards fell from 11 and 12 per run to between 0 and 2 across the four runs since, and quiz answer keys went from 0.80 to 0.93. The validator now discriminates: rejected quiz questions score 0.54 and 0.62 faithful against 0.93 for the ones shipped. Two prompt changes went with it (keyed claims must be stated, not inferred; true/false statements must restate or be contradicted by the video), but by themselves they didn't move the overall number outside noise.
- **A stricter validator ships shorter quizzes, so it tops up.** A 10-question podcast quiz came back with 7, 9, 10 and 5 questions across four runs. If validation leaves a quiz short, it now generates once more for just the shortfall, validates it the same way, and stops (`TOP_UP_ROUNDS = 1`). Both runs then shipped the full 30. On longer videos that roughly doubles the generation calls, all on gpt-4o-mini.
- **What's left:** about 2 in 30 shipped quiz questions still have a debatable key, mostly multi-select questions where a distractor is arguably true. Shipped flashcard faithfulness is 0.83-0.93 across four runs, within noise of before: the flashcard fix restored full decks and stopped false rejections, but it didn't measurably make cards more faithful. Grading is deterministic, so a bad key marks a correct answer wrong.

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
