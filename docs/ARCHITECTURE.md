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

1. Group raw cues into sentence-ish units (cues are often fragmentary).
2. Embed each unit.
3. Find semantic breakpoints: compute cosine distance between consecutive units and cut where distance exceeds a percentile threshold (configurable, start around the 90th percentile). This is the same idea as semantic chunking, applied at a coarser scale.
4. Merge segments shorter than a minimum duration (~60s) into their neighbour so you don't end up with dozens of micro-topics.
5. Send each resulting segment's text to the LLM for a short topic label and a 1–2 sentence summary. Store both.

**Output per segment:** `start_time`, `end_time`, `label`, `summary`, `order_index`.

The labels become the checkboxes in the flashcard and quiz config forms. The summaries are what the generation pipelines consume instead of raw transcript, which is what keeps whole-video generation inside the context window.

**Tunables worth exposing in config:** breakpoint percentile, minimum segment duration, max segments per video. These are the knobs you will iterate on, so make them settings, not magic numbers.

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
- For multiple choice: exactly one correct option; no duplicate options; distractors must not be arguably correct.
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

**Retrieval** — build a small golden set (20–30 question/expected-chunk pairs across 3–4 videos). Measure recall@k, MRR, and hit rate. Use it to compare chunk sizes, `k`, and hybrid vs pure vector.

**Generation faithfulness** — LLM-as-judge scoring each generated card or question against its cited source: is it supported, is it answerable from the video, is exactly one option correct.

**Segmentation** — harder to score automatically. Manual review of segment boundaries on a couple of videos is acceptable; note it as a limitation rather than pretending otherwise.

Store results in a versioned file under `api/eval/results/` so improvements are visible over time. Being able to say "hybrid retrieval raised recall@5 from 0.71 to 0.86" is worth more than any feature.
