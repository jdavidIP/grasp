# Roadmap

Build order. Each phase should leave the app in a working state.

## Phase 1 — Skeleton

- `docker-compose.yml` with `api`, `db` (postgres 16 + pgvector), `web`.
- FastAPI app with health check; Vite + React + TS app that reaches it.
- Alembic wired up; `CREATE EXTENSION vector` in the first migration.
- `videos` table and `GET`/`POST`/`DELETE /videos`, with ingestion stubbed (create row, mark `ready` immediately).
- Frontend: library page listing videos, add-by-URL form, delete.

Done when you can add and remove videos through the UI.

## Phase 2 — Ingestion

- Transcript fetch via `youtube-transcript-api`, `yt-dlp` + Whisper fallback.
- Metadata fetch.
- Background task with `status` transitions and error capture.
- Frontend polls until ready; shows a clear failure state.

Skip segmentation for now — store the raw transcript.

## Phase 3 — Segmentation, chunking, embedding

- `transcript_segments` and `transcript_chunks` tables with HNSW index.
- Semantic breakpoint detection, short-segment merging, LLM topic labelling and summaries.
- Chunk within segments, batch-embed, store.
- `POST /videos/{id}/reprocess` so you can iterate on parameters without re-fetching.
- Frontend: video detail page showing the topic list.

This is the phase to spend real time on. Run it against three or four genuinely different videos (a lecture, a rambling podcast, a short tutorial) and look at the segment boundaries yourself.

## Phase 4 — Chat

- Vector retrieval, then hybrid, then reranking — in that order, measuring each.
- Grounded answer generation with an explicit "not covered" path.
- `chat_messages` persistence.
- Frontend: chat panel, source chips with timestamps, YouTube iframe that seeks on click.

Done when clicking a citation jumps the player to the right moment.

## Phase 5 — Flashcards

- `flashcard_decks` and `flashcards` tables.
- Config form: count, scope, topic checkboxes from segments, difficulty, style.
- Summarize-then-generate pipeline with JSON schema output.
- Validation pass: grounding check, dedupe, count enforcement.
- Frontend: config modal, deck list, card review view with flip and timestamp link.

## Phase 6 — Quizzes

- `quizzes`, `quiz_questions`, `quiz_options`, `quiz_attempts`, `quiz_answers`.
- Config form with question types (`multiple_choice`, `multi_select`, `true_false`), options per question, difficulty.
- Generation with distractors drawn from other segments. The answer key is produced at generation time.
- Validation: per-type correct-option counts, no duplicate options, no arguably-correct distractors.
- Attempt submission with deterministic grading (selected set must equal the correct set — no LLM call), results view with explanations and source links.
- Frontend: take-quiz flow, results, attempt history.

## Phase 7 — Evaluation

- Golden set of 20–30 question/chunk pairs across several videos.
- Retrieval metrics: recall@k, MRR, hit rate.
- Faithfulness judging for generated cards and questions.
- Results committed under `api/eval/results/` with dates, so the improvement curve is visible.
- Write the numbers into the README.

## Phase 8 — Polish

- Loading and empty states throughout.
- Error surfaces that explain what went wrong.
- README with architecture diagram, design decisions, eval results, and an explicit "what I deliberately left out and why" section.

## Deliberately deferred

Only if everything above is done and working: spaced repetition, cross-video questions, export, deck editing, multi-language support.
