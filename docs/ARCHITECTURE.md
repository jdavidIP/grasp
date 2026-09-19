# Architecture

## Overview

```
Add video (URL)
   ↓
Fetch transcript  →  captions if available, else yt-dlp + Whisper
   ↓
Topic segmentation  →  semantic breakpoints, LLM-labelled topics
   ↓
Chunking + embedding  →  overlapping chunks with timestamps
   ↓
Postgres + pgvector
   ↓
   ├── Chat section       →  retrieve → grounded answer + timestamps
   ├── Flashcards section →  config form → summarize → generate deck
   └── Quizzes section    →  config form → summarize → generate quiz
```

There is no LLM-based query router. The three sections are separate UI surfaces hitting separate endpoints, so intent is explicit. What routes *within* a section is the user's config (which topics, whole video or not).

---

## 1. Ingestion

Triggered by `POST /videos`. Runs as a background task; the video row is created immediately with `status = "pending"` so the UI can poll.

**Steps**

1. Parse the YouTube URL for a video ID. Reject anything that isn't a valid ID.
2. Fetch metadata (title, channel, duration, thumbnail) — `yt-dlp` metadata-only is fine.
3. Get the transcript:
   - Try `youtube-transcript-api` for existing captions. Fast, free, no audio download.
   - If unavailable, download audio with `yt-dlp` and transcribe with the Whisper API.
   - Store which path was used in `videos.transcript_source` — it affects transcript quality and is worth surfacing.
4. Normalize into a list of `{start, end, text}` cues.
5. Run segmentation, chunking, embedding (below).
6. Set `status = "ready"`, or `status = "failed"` with an error message.

**Failure modes to handle explicitly:** captions disabled, video unavailable/private, age-restricted, non-target language, video longer than a configured max duration.

---

## 2. Topic segmentation

This is the step most implementations skip, and it is the one that carries the most weight here. Podcasts and long-form video wander; fixed-size chunks mix unrelated ideas, which produces vague answers and bad flashcards.

**Approach**

1. Group raw cues into sentence-ish units (cues are often fragmentary). A unit closes on sentence-ending punctuation, a pause in speech, or after 15 seconds, whichever comes first. The cap matters: auto-generated captions have no punctuation and almost no pauses, and without it a single "sentence" swallowed minutes of speech, which left breakpoint detection nothing to compare. A 3-hour podcast came out as 4 topics ([#15](https://github.com/jdavidIP/grasp/issues/15)).
2. Embed each unit.
3. Find semantic breakpoints: compute cosine distance between consecutive units and cut where distance exceeds a percentile threshold (configurable, start around the 90th percentile). This is the same idea as semantic chunking, applied at a coarser scale.
4. Merge segments shorter than a minimum duration into their neighbour so you don't end up with dozens of micro-topics. The minimum is `max(60s, 1.5% of the video)`. A single fixed minimum can't serve both extremes: 60 seconds leaves a 3-hour podcast with ~30 fragmentary topics, while the ~2 minutes that suits the podcast would fold a 10-minute tutorial's genuine 1-minute "Functions" topic into its neighbour. The topic list is a menu for a person, so a rambling podcast should offer ~20 recognisable topics, not every sub-topic.
5. Send each resulting segment's text to the LLM for a short topic label and a 1–2 sentence summary. Store both.

**Output per segment:** `start_time`, `end_time`, `label`, `summary`, `order_index`.

The labels become the checkboxes in the flashcard and quiz config forms. The summaries are what the generation pipelines consume instead of raw transcript, which is what keeps whole-video generation inside the context window.

**Tunables worth exposing in config:** breakpoint percentile, minimum segment duration (seconds and fraction of video), max segments per video. These are the knobs you will iterate on, so make them settings, not magic numbers.

---

## 3. Chunking and embedding

Segmentation gives topical boundaries; chunking gives retrievable units inside them.

- Chunk **within** segment boundaries — never let a chunk straddle two topics.
- Target ~400–600 tokens with ~15% overlap.
- Each chunk stores: `video_id`, `segment_id`, `start_time`, `end_time`, `text`, `embedding`.
- Embed with `text-embedding-3-small` (1536 dims). Batch the calls.

Storing `segment_id` on the chunk is what lets you filter retrieval to selected topics with a plain `WHERE` clause alongside the vector search.

---

## 4. Retrieval (chat section)

`POST /videos/{id}/chat`

1. Embed the user's question.
2. Vector search over that video's chunks, `k = 8` initially.
3. Optionally add keyword search (Postgres full-text) and fuse results — hybrid retrieval measurably helps when the question contains names or jargon the embedding flattens.
4. Rerank the candidates down to 4–5 (a cross-encoder, or an LLM scoring pass) before generation.
5. Generate the answer with a prompt that requires grounding and permits "not covered in this video."
6. Return the answer plus the source chunks with their timestamps.

**Conversation memory:** send recent turns, but re-retrieve on every question. Do not rely on prior context to answer a new question — that is how ungrounded answers creep in.

**The no-answer case matters.** A system that admits the video doesn't cover something is more impressive than one that always produces prose. Test for it deliberately.

### Broad vs specific questions

There is no app-level query router (see `CLAUDE.md` — intent is decided by which section of the UI the user is in). But a smaller version of the same problem still exists *inside* the chat endpoint: a user can type "summarize this video" or "what are the main points?" into the same chat box they use for "what did they say about X at minute 10?" Standard top-k retrieval is built for the second kind of question and handles the first one badly — it pulls a handful of chunks and produces a thin, partial summary of a few topics rather than the whole video.

Handle this with a lightweight strategy check at the top of `POST /videos/{id}/chat`, before retrieval runs:

1. Classify the question as `specific` or `broad`. A cheap heuristic covers most cases (keyword/pattern match on things like "summarize," "overview," "main points," "what is this video about," or a question with no concrete noun to anchor a search on) with a fallback to a single small LLM call when the heuristic is unsure. This is a much narrower decision than the old app-level router — it picks a *retrieval strategy* for one endpoint, not an app section — so it doesn't reintroduce the misrouting risk discussed earlier.
2. `specific` → the normal path: embed the question, vector search, rerank, generate.
3. `broad` → reuse the same map-reduce-over-segments approach the flashcard/quiz pipelines already use: pull all segment summaries for the video, generate the answer from those instead of individual chunks.

Both paths return the same response shape (`answer`, `sources`, `grounded`); for the `broad` path, `sources` lists the segments used rather than individual chunks. Worth testing explicitly once chat is built — try "what's this video about?" and confirm it doesn't just answer from the first few chunks it happens to retrieve.

---

## 5. Generation pipelines (flashcards and quizzes)

Both follow the same shape and differ only in the output schema and prompt.

```
Config form  →  select segments  →  summarize  →  generate  →  validate  →  store
```

**Step 1 — Config.** The user picks scope and parameters before anything runs. See `docs/API.md` for the exact payloads. Topics presented are the segment labels from ingestion.

**Step 2 — Select segments.** Whole video means all segments; selected topics means those segments only.

**Step 3 — Build context.** Map-reduce rather than stuffing:
- For a small number of segments, pass segment summaries plus their full chunk text.
- For whole-video requests on long content, pass segment summaries only, plus the top chunks per segment by centrality. This is what keeps a three-hour podcast inside the context window.

**Step 4 — Generate.** One LLM call with a strict JSON output schema. Request slightly more items than asked for, so validation can drop weak ones and still hit the requested count.

**Step 5 — Validate.** This is where quality actually comes from:
- Every item must cite a `segment_id` and a timestamp range.
- Reject items whose claimed source text doesn't support them (a second LLM call scoring faithfulness, or embedding similarity between the item and its cited chunk).
- For quiz questions: per-type correct-option counts (`multiple_choice` and `true_false` exactly one; `multi_select` at least one correct and at least one incorrect); no duplicate options; distractors must not be arguably correct. The model returns the answer key with the question, so grading later is a set comparison with no second LLM call.
- Deduplicate near-identical items by embedding similarity.

**Step 6 — Store.** Persist the deck or quiz with its config so the user can see how it was generated.

### Distractor generation

The default failure mode is distractors that are obviously wrong, which makes a quiz trivial. The fix that works: draw distractors from **things actually said elsewhere in the video that do not answer this question**. They are topically plausible and verifiably wrong. Give the model the other segments' summaries as distractor source material and instruct it accordingly.

### Difficulty

Define it concretely rather than asking the model for "hard":
- **Easy** — the answer is stated directly in one chunk.
- **Medium** — the answer requires combining two statements, or recalling a specific detail.
- **Hard** — the answer requires inference across segments, or distinguishing between closely related points made in the video.

---

## 6. Evaluation

Do not skip this. It is the clearest differentiator against the many similar projects.

Both evals are offline CLI tools in `api/app/eval/`, run inside the `api` container. Each writes a dated JSON file to `api/eval/results/` (`<eval>-YYYY-MM-DD[-label].json`) that is committed, so the improvement curve lives in git history. Current numbers are in the README.

### Golden set

`api/eval/golden_set.json` has question → **time span** pairs (`youtube_id`, `[start, end]` in seconds) across three deliberately different videos: a punctuated-caption lecture, a 3-hour auto-captioned podcast, and a 10-minute auto-captioned tutorial. Entries with `span: null` are out-of-scope questions the video doesn't answer.

- **Spans, not chunk ids.** Chunk ids change every time a video is reprocessed, and chunk boundaries move whenever chunking parameters change. Scoring against timestamps keeps the golden set valid across reprocessing, and lets different chunk sizes be compared on the same questions. The cost: a span holds one answer location, so a question also answered elsewhere in the video gets scored as a miss. Review removes those questions (it reworded one, `BDqvzFY72mg-16`).
- **Drafted by LLM, reviewed by a human.** `python -m app.eval.draft_golden <youtube_ids>` samples evenly spaced 40-second transcript windows, and gpt-4o writes one paraphrased question per window. Paraphrasing matters: questions that copy the transcript's wording would make keyword search look better than it is. The prompt gets the video's topic list and must skip incidental content: logistics, classroom remarks, "what this course will cover", small talk. Every entry is then reviewed by hand. Questions are never edited just because retrieval missed them, since that would bias the set toward the system.
- **Speaker slips.** The transcript is the source of truth, but speakers misspeak (the lecture says "the Soviet Union invaded Ukraine"). The drafter flags apparent slips in a `note` and words the question so it doesn't depend on the slip.
- **Out-of-scope questions** have to be adjacent to the video's subject to be a real test. Each one is grep-checked against the transcript. Two drafted podcast questions turned out to be covered and were replaced.

### Retrieval

`python -m app.eval.retrieval [--label X]` runs every in-scope question through the production retrieval functions (`vector`, `hybrid`, `hybrid_rerank`) with production parameters. A retrieved chunk is a hit when its time range overlaps the golden span.

- **hit_rate@k:** fraction of questions with a hit in the top k.
- **recall@k:** mean fraction of the span's *duration* covered by the union of the top-k chunks. This depends only on timestamps, so it is comparable across chunk sizes.
- **MRR:** mean of 1 / rank of the first hit, where a miss counts as 0.
- **Out-of-scope decline rate:** each span-less question runs through the full chat path. A decline is `grounded: false`.

**Limitations:**
- With ~500-token chunks, a 10-minute video has 6 chunks, so @5 and @8 saturate for short videos. hit@1 and MRR are the metrics that separate strategies.
- The rerank strategy is an LLM call, so it isn't deterministic. Two identical baseline runs differed by 0.01 on recall@1. With 26 questions, one question is worth ~0.04 at @1.
- Every golden question is *specific*. Broad questions ("what is this video about?") take a different chat path and are not measured yet.
- Both lecture misses in the baseline were answers diluted inside a chunk mostly about something else. That is the case for testing smaller chunks ([#17](https://github.com/jdavidIP/grasp/issues/17)).

### Generation faithfulness

`python -m app.eval.faithfulness [--label X]` generates one deck and one quiz per golden-set video from fixed configs, using the production pipelines. The pipelines' optional `trace` argument exposes the intermediate candidates. gpt-4o judges every candidate against the **raw transcript of the segment it cites**, rather than the summary and excerpts the generator saw.

- **Why gpt-4o and not the generator model:** a model grading its own output inflates scores. Eval tooling passes `model=llm.EVAL_MODEL` to the single LLM wrapper.
- **Checks:** `supported` (every claim is in the transcript), `answerable` (someone who watched could answer it), and, for quizzes, `key_correct` (every keyed option is right and no distractor is actually true, whether per the transcript or plainly in general). `faithful` means all checks pass. `speaker_slip` is tracked separately: an item that faithfully repeats a misspoken fact is flagged, not failed.
- **Reason before verdict:** the judge writes its reasoning before the booleans. With the verdict first, the flags contradicted their own reasons.
- **Stages:** rates are reported for `raw` (all candidates), `rejected` (what the pipeline's own LLM validation dropped), and `kept` (what a user sees). This measures what validation actually buys.
- **Noise:** there are ~30 items per group, and generation is stochastic (fresh items every run), so one item moves a rate by ~0.03. Two runs differing only in judge wording differed by 0.09 on kept-flashcard faithfulness. Treat differences under ~0.1 as noise until repeated runs say otherwise.

### Segmentation

Segmentation is not scored automatically. Boundaries are reviewed by hand, and that is a limitation. Reviewing the three eval videos found that auto-captioned videos collapsed into a few huge segments: a 3-hour podcast became 4 segments and a 10-minute tutorial became 1, because punctuation-free captions defeated sentence grouping ([#15](https://github.com/jdavidIP/grasp/issues/15), fixed in §2). The golden set survived the fix unchanged because it scores timestamps, which let both evals measure the change directly: faithfulness of shipped items rose (flashcards 0.81 → 0.86, quizzes 0.80 → 0.86), and retrieval hit@1 dipped (0.88 → 0.81) because every chunk boundary moved.

### Rate limits

gpt-4o calls in the eval tools run sequentially. Running them in parallel exceeds the account's tokens-per-minute limit.
