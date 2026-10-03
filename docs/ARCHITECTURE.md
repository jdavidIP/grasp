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
3. Find semantic breakpoints: for each gap between units, compute the cosine distance between the speech in a window before it and a window after it (`segmentation_window_seconds`, 20s a side, whole units, embeddings summed), and cut where the distance exceeds a percentile threshold (configurable, start around the 90th percentile). This is the same idea as semantic chunking, applied at a coarser scale.

   **Why a window, not unit to unit** ([#38](https://github.com/jdavidIP/grasp/issues/38)). Comparing each unit only with the next let a lone filler unit decide boundaries. The lecturer pauses around "what's the word?", which becomes its own 0.8s unit with a near-meaningless embedding, so it scored as a topic change on both sides. The boundary landed there, ~30s before the real change ("now let's fast-forward three decades…"), and the Cold War optimism passage ended up in a chunk mostly about the far right, which no search mode retrieved. It wasn't a one-off: 6 of the lecture's 14 boundaries sat next to a unit of 4 words or fewer, which make up 11% of its units but 44% of its raw breakpoints. With the window, that fell to 3 of 14 (podcast: 2 of 19 to 1 of 22; tutorial unchanged at 0 of 3). The 20s was chosen before measuring, and 30s gave nearly the same boundaries. Keeping only local peaks of the distance curve was also tried and made no material difference, so it isn't used.

   **Measured** (two runs each, 28 questions): production retrieval hit@1 went from 0.89 and 0.86 to 0.96 and 0.93, hit@5 from 0.96 to 1.00, and MRR from 0.92 and 0.91 to 0.98 and 0.96. Every mode improved, including deterministic vector search (hit@1 0.79 to 0.82), and the gain wasn't only the target question: two podcast questions reached rank 1 in both runs, while one slipped from 1 to 2 in one run. Chat and flashcards were unchanged. Shipped quiz faithfulness fell from a mean of 0.97 (six runs on the old segments) to 0.92 (four runs), within run-to-run noise but at the low end in every run; the cause isn't established (§6, Generation faithfulness). **The trade:** the topic list is coarser in places. The lecture's far-right material is one 11-minute topic instead of five, and the tutorial's 1-minute "Functions" topic is now part of "Loops and Functions". That's acceptable: retrieval works on chunks, and each passage now sits in a chunk about it. One boundary still lands on noise ("(student speaking faintly)").
4. Merge segments shorter than a minimum duration into their neighbour so you don't end up with dozens of micro-topics. The minimum is `max(60s, 1.5% of the video)`. A single fixed minimum can't serve both extremes: 60 seconds leaves a 3-hour podcast with ~30 fragmentary topics, while the ~2 minutes that suits the podcast would fold a 10-minute tutorial's genuine 1-minute topics into their neighbours. The topic list is a menu for a person, so a rambling podcast should offer ~20 recognisable topics, not every sub-topic.
5. Send each resulting segment's text to the LLM for a short topic label and a 1–2 sentence summary. Store both.

6. Check each segment's full text for speaker slips (below) and store them with it.

**Output per segment:** `start_time`, `end_time`, `label`, `summary`, `order_index`, `slips`.

The labels become the checkboxes in the flashcard and quiz config forms. The summaries are what the generation pipelines consume instead of raw transcript, which is what keeps whole-video generation inside the context window.

**Tunables worth exposing in config:** breakpoint percentile, breakpoint comparison window, minimum segment duration (seconds and fraction of video), max segments per video. These are the knobs you will iterate on, so make them settings, not magic numbers.

### Speaker slips

Speakers misspeak and captions mishear: the lecture says "the Soviet Union invaded Ukraine" (Russia), and the tutorial's captions write "accept" for `except`. The content generated from the transcript should state the intended fact and name the slip, not repeat it ([#18](https://github.com/jdavidIP/grasp/issues/18), [#34](https://github.com/jdavidIP/grasp/issues/34)). That only works if something notices the slip. At ingestion and reprocess, `detect_slips` (`app/ingestion/slips.py`) checks each segment's full transcript and the result is stored as `transcript_segments.slips`, `[{said, meant, reason}]`. If a slip-check call fails, ingestion fails with the same user-facing message as any other LLM step, rather than storing an empty list that would look like "no slips".

- **Detection is its own step, not something the answer model does in passing.** Telling the chat model to catch slips while it answers failed on every try (0/6, including the easy "angle brackets" one), because it treats the excerpts as the truth. On its own with a whole segment, gpt-4o-mini still missed every known slip and invented some, while gpt-4o found all three. So detection runs once per segment, on gpt-4o.
- **Two passes, and only what both agree on is kept.** A single gpt-4o pass found every known slip, but about a third of its 45 "slips" were wrong or needless corrections, and some would teach something false ("Georgia and Ukraine" → "Georgia and Moldova"; Hubble's 1929 → 1924). Those rarely repeat identically, so a slip survives only if a second, independent pass flags the same words with the same correction. Across two samples this kept 16 and 11 slips, none a wrong correction. Over four ingests of the eval videos it caught 8 of the 12 known-slip opportunities (the Soviet Union one 2 of 4, "angle brackets" 2 of 4, "accept" 4 of 4). A missed slip costs less than a wrong one: chat just repeats the transcript, which is what it did before, and the current lecture ingest is one such miss. Agreement stops *random* wrong corrections, not systematic ones: both passes can make the same mistake, and one ingest kept the podcast's "295 days" corrected to "280" while the speaker is arguing against 280 (about 1 wrong of ~45 kept).
- **A quote must be real.** `parse_slips` drops any slip whose `said` doesn't occur in the segment (ignoring case and punctuation).
- **A slip must be slip-sized.** `said` and `meant` are capped at 12 words and 200 characters. Both reach the chat prompt as a trusted correction and the note shown to the viewer, and they are model output derived from an untrusted transcript, so a whole quoted passage or an injected instruction is dropped rather than stored.
- **Cost:** two gpt-4o calls per segment. For the three eval videos that was about 106k prompt tokens and just under 3 minutes. The calls run one at a time *across the whole process* (a lock in `slips.py`): three videos reprocessed at once each making their own sequential calls still exceeded the tokens-per-minute cap, and the 3-hour podcast's reprocess failed on it.

**How chat uses them.** Chat passes the model the stored slips whose quoted words appear in the passages it shows the model, as a numbered list. The model writes the intended fact, never the slip, and returns the numbers of the slips it relied on in `slips_used`. The app then appends a note to the answer — *(The video says "angle brackets" here; the speaker means "square brackets".)* — so a viewer isn't confused when the video says something else. The app writes the note because the model wouldn't: told to name the slip itself, it silently corrected the fact every time (0/6 across two prompt wordings). Picking slips from a numbered list is the part gpt-4o-mini does reliably.
- **The list must not read as more content.** The first wording ("if your answer relies on one, …") made chat answer an out-of-scope question with a listed slip's material: "best practices for file I/O" got an answer about the tutorial's try/except block, because "try and accept" → "try and except" was in the list. With the same retrieved chunks it answered 40 of 76 samples; without the slip additions, 0 of 28. The system prompt now says the list is only a correction aid that doesn't bear on whether the video answers the question: 1 of 28 after. A decline never gets a note, even if the model lists a slip.
- **Known limit: notes can over-attach.** The model sometimes marks a slip as used when its answer doesn't rely on it, so a note lands on an answer that never mentions the slipped fact. The correction is still right, just unneeded; not worth a guard until it shows up in real use (checking the answer for the corrected words misses paraphrases like "try-except block").
- **Known limit: broad answers rarely get slips.** The broad path shows the model segment summaries, not transcript text, and a slip is only passed when its quote appears in what the model sees. Summaries paraphrase, so few quotes survive: 1 of the 13 slips stored for the eval videos. Matching against the segments' transcript instead would list slips whose material the model never sees. Broad answers are summary-level, so a slip mostly matters in specific answers.

Video transcripts are never fully accurate, so none of this aims for perfection: what the video gets wrong and detection misses, chat repeats. The bar is that the slip layer never makes an answer *worse* than the transcript alone.

**Considered and not chosen: three passes, majority vote.** The two-pass rule trades recall for precision. If a single pass catches a given real slip with probability *p* (measured about 0.75–0.85 for "the Soviet Union invaded Ukraine": 5 of 6 raw passes), requiring two passes to agree keeps it with probability *p*² ≈ 0.56–0.72. A third pass with a 2-of-3 majority raises that to 3*p*² − 2*p*³ ≈ 0.84–0.94.
- **For it:** more real slips reach chat. The ones two-pass drops are real and useful ("angle brackets", Röntgen's name).
- **Against it:** a wrong correction that a single pass makes a quarter of the time (Mitterrand → Chirac appeared in 1 of 4 passes) would be kept about 16% of the time instead of about 6%. That's a false fact presented as the speaker's intended meaning, which is worse than repeating the transcript. It also costs 50% more gpt-4o at ingestion (~160k prompt tokens for the eval videos) and makes ingestion 50% slower.
- **Why two-pass for now:** the video is the source of truth. A miss leaves chat repeating what the video said; a wrong correction contradicts the video with something false.
- **Reconsider if:** users are demonstrably misled by missed slips, or a stronger slip-check model makes single passes more precise (lowering the 16%). The change is small: a third pass in `detect_slips` and a majority rule in place of `agreed_slips`. Measure both numbers again over at least two ingests before switching.

---

## 3. Chunking and embedding

Segmentation gives topical boundaries; chunking gives retrievable units inside them.

- Chunk **within** segment boundaries — never let a chunk straddle two topics.
- Target **~250 tokens** with ~15% overlap.
- Each chunk stores: `video_id`, `segment_id`, `start_time`, `end_time`, `text`, `embedding`.
- Embed with `text-embedding-3-small` (1536 dims). Batch the calls.

Storing `segment_id` on the chunk is what lets you filter retrieval to selected topics with a plain `WHERE` clause alongside the vector search.

**Chunk size was tuned down from an initial ~500-token target** ([#17](https://github.com/jdavidIP/grasp/issues/17)). At 500 tokens, two lecture questions' answers sat inside a chunk that was mostly about something else, so the chunk's embedding pointed away from the answer. Halving the target to 250 tokens, reprocessed and measured twice against the same golden set: production (hybrid + rerank) hit@1 went from a 0.81–0.85 range to 0.88–0.92, and MRR from 0.88–0.90 to 0.92–0.94, both non-overlapping improvements. One of the two known misses — an exact-name match ("Marshall Plan") — is now retrieved even by pure vector search, at rank 4. The other is not: its answer sits inside a segment whose *entire* transcript is only 167 tokens, well under even the 250-token target, so chunking (which never splits below what a segment already contains) has nothing left to shrink — the dilution is a segmentation-boundary problem, not a chunk-size one. The cost side: roughly 1.8x as many chunks to embed (the 10-minute tutorial went from 6 chunks to 11) and less transcript per chunk kept for chat generation (5 reranked chunks now carry ~1,250 tokens of context instead of ~2,500). At 250 tokens the chat eval scores answers 1.00 supported and 1.00 answering the question (§6, Chat answers), though there's no 500-token chat run to compare against. Full numbers: [`retrieval-2026-09-23-chunk500-run1.json`](../api/eval/results/retrieval-2026-09-23-chunk500-run1.json) / [`-run2`](../api/eval/results/retrieval-2026-09-23-chunk500-run2.json) vs [`-chunk250-run1`](../api/eval/results/retrieval-2026-09-23-chunk250-run1.json) / [`-run2`](../api/eval/results/retrieval-2026-09-23-chunk250-run2.json).

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

1. Classify the question as `specific` or `broad` with one gpt-4o-mini call (`app/prompts/chat_classify.py`) on every question. The test is scope: does answering need the whole video, or one part of it? When unsure, it answers `specific`. This is a much narrower decision than the old app-level router — it picks a *retrieval strategy* for one endpoint, not an app section — so it doesn't reintroduce the misrouting risk discussed earlier.
2. `specific` → the normal path: embed the question, vector search, rerank, generate.
3. `broad` → reuse the same map-reduce-over-segments approach the flashcard/quiz pipelines already use: pull all segment summaries for the video, generate the answer from those instead of individual chunks.

Both paths return the same response shape (`answer`, `sources`, `grounded`); for the `broad` path, `sources` lists the segments used rather than individual chunks. Worth testing explicitly once chat is built — try "what's this video about?" and confirm it doesn't just answer from the first few chunks it happens to retrieve.

**Why no keyword heuristic** ([#37](https://github.com/jdavidIP/grasp/issues/37)). The first version used one: a keyword match ("summarize", "overview") meant broad, any content word meant specific, and only the rest reached the LLM. Wording fails both ways. "What will I learn from this tutorial?" has content words, so 3 of the original 6 broad golden questions got few-chunk answers. "Summarize what they said about James Randi" has the keyword but is about one topic. Dropping the shortcut costs one small call per question (about 300 prompt tokens) and its latency, which is cheap next to a wrong-path answer that the judge can't detect (§6).

**Tradeoff in the prompt: subject breadth vs video breadth.** The classifier's first prompt called a question broad when it had "no concrete detail to search for", and it sent wide-ranging subject questions ("Why does the idea of psychic abilities captivate people?") to the whole-video path, about 0.3 of specific questions. The prompt now says a question can be wide-ranging in subject and still be specific, and defaults to specific when unsure. A wrongly specific answer is a thin overview; a wrongly broad one answers a single topic from topic summaries and loses its detail. Specific questions are the common case, so the default protects them. Measured over two chat eval runs: broad 0.92 and specific 0.00 `routed_broad`. The remaining miss names a field ("What Python concepts does this teach?").

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
- Reject items whose cited source doesn't support them, with a second LLM call that checks each item against the **full transcript of the segment it cites**, one call per cited segment, in parallel. Do not audit against the same summary-plus-excerpts context the generator saw: that validator can't verify items grounded elsewhere in the segment (it rejects good ones) and can't tell a stated fact from one filled in from general knowledge (it keeps bad ones). Measured in [#16](https://github.com/jdavidIP/grasp/issues/16): 11 and 12 good cards wrongly rejected per run before, 0 to 2 per run over four runs after.
- For quiz questions: per-type correct-option counts (`multiple_choice` and `true_false` exactly one; `multi_select` at least one correct and at least one incorrect); no duplicate options; distractors must not be arguably correct. The model returns the answer key with the question, so grading later is a set comparison with no second LLM call.
- **Speaker slips are named, never silently corrected.** If an item would otherwise be built on an apparent slip in the transcript (wrong name, date, number), the generation prompt has it avoid that item or state the corrected fact and name the slip — for flashcards, in a `note` column; for quizzes, folded into the existing `explanation`. The validator's own prompt has the matching exception, or it would reject a correctly-noted item as unsupported. Measured in [#18](https://github.com/jdavidIP/grasp/issues/18): zero known slips stated as fact across 148 sampled items over 2 eval runs.
- Deduplicate near-identical items by embedding similarity.
- If validation and dedupe leave a quiz short of the requested count, generate once more for just the shortfall (telling the model what is already kept), validate it the same way, and stop (`TOP_UP_ROUNDS = 1`). A stricter validator rejects more, and a 10-question podcast quiz otherwise shipped as few as 5.

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

The evals are offline CLI tools in `api/app/eval/`, run inside the `api` container. Each writes a dated JSON file to `api/eval/results/` (`<eval>-YYYY-MM-DD[-label].json`) that is committed, so the improvement curve lives in git history. Current numbers are in the README. Each eval refuses to start unless every golden-set video exists and is `ready`: a video in the middle of a reprocess has no segments or chunks yet, and would be scored as bad answers instead of reported as unprocessed.

The chat and faithfulness evals also report **tokens per feature**. `llm.track_usage()` is a context manager that totals prompt and completion tokens per model for every call made inside it. Every OpenAI call goes through the one wrapper, so the eval wraps each feature's calls and nothing in the pipelines had to change. The results file's `usage` key holds the totals, with the judge counted separately from the feature it judges.

### Golden set

`api/eval/golden_set.json` has question → **time span** pairs (`youtube_id`, `[start, end]` in seconds) across three deliberately different videos: a punctuated-caption lecture, a 3-hour auto-captioned podcast, and a 10-minute auto-captioned tutorial. Entries with `span: null` are out-of-scope questions the video doesn't answer.

- **Spans, not chunk ids.** Chunk ids change every time a video is reprocessed, and chunk boundaries move whenever chunking parameters change. Scoring against timestamps keeps the golden set valid across reprocessing, and lets different chunk sizes be compared on the same questions. The cost: a span holds one answer location, so a question also answered elsewhere in the video gets scored as a miss. Review removes those questions (it reworded one, `BDqvzFY72mg-16`).
- **Drafted by LLM, reviewed by a human.** `python -m app.eval.draft_golden <youtube_ids>` samples evenly spaced 40-second transcript windows, and gpt-4o writes one paraphrased question per window. Paraphrasing matters: questions that copy the transcript's wording would make keyword search look better than it is. The prompt gets the video's topic list and must skip incidental content: logistics, classroom remarks, "what this course will cover", small talk. Every entry is then reviewed by hand. Questions are never edited just because retrieval missed them, since that would bias the set toward the system.
- **Speaker slips.** The transcript is the source of truth, but speakers misspeak (the lecture says "the Soviet Union invaded Ukraine"). The drafter flags apparent slips in a `note` and words the question so it doesn't depend on the slip.
- **Out-of-scope questions** have to be adjacent to the video's subject to be a real test. Each one is grep-checked against the transcript. Two drafted podcast questions turned out to be covered and were replaced.
- **Broad questions** (`"kind": "broad"`, `span: null`) ask about the whole video, which chat answers from segment summaries rather than retrieved chunks. The retrieval eval skips them; the chat eval uses them. They are hand-written, four per video: one worded with a summary keyword ("overview", "summarize") and three worded naturally ("What will I learn from this tutorial?"), so they measure the router as well as the answer. The reverse case has two specific questions (`-keyword-1`): worded with a summary keyword but scoped to one topic, reusing an existing question's span. The retrieval eval scores those two as well.

### Retrieval

`python -m app.eval.retrieval [--label X]` runs every in-scope question through the production retrieval functions (`vector`, `hybrid`, `hybrid_rerank`) with production parameters. A retrieved chunk is a hit when its time range overlaps the golden span.

- **hit_rate@k:** fraction of questions with a hit in the top k.
- **recall@k:** mean fraction of the span's *duration* covered by the union of the top-k chunks. This depends only on timestamps, so it is comparable across chunk sizes.
- **MRR:** mean of 1 / rank of the first hit, where a miss counts as 0.
- **Out-of-scope decline rate:** each span-less question runs through the full chat path. A decline is `grounded: false`.

**Limitations:**
- With 250-token chunks, a 10-minute video has 11 chunks, so @5 and @8 saturate for short videos. hit@1 and MRR are the metrics that separate strategies.
- The rerank strategy is an LLM call, so it isn't deterministic. Two identical baseline runs differed by 0.01 on recall@1. With the 26 questions those runs used, one question is worth ~0.04 at @1.
- Broad questions ("what is this video about?") have no span, so retrieval doesn't score them. The chat eval covers them instead.
- The two baseline misses were both answers diluted inside a chunk mostly about something else. One was fixed by the 250-token chunk size tuned in §3 ([#17](https://github.com/jdavidIP/grasp/issues/17)). The other sat in a segment already under 250 tokens because a segment boundary had landed on a filler phrase; the windowed boundaries in §2 fixed it ([#38](https://github.com/jdavidIP/grasp/issues/38)). Every specific question is now retrieved in the top 5.

### Generation faithfulness

`python -m app.eval.faithfulness [--label X]` generates one deck and one quiz per golden-set video from fixed configs, using the production pipelines. The pipelines' optional `trace` argument exposes the intermediate candidates. gpt-4o judges every candidate against the **raw transcript of the segment it cites**, rather than the summary and excerpts the generator saw.

- **Why gpt-4o and not the generator model:** a model grading its own output inflates scores. Eval tooling passes `model=llm.EVAL_MODEL` to the single LLM wrapper.
- **Checks:** `supported` (every claim is in the transcript), `answerable` (someone who watched could answer it), and, for quizzes, `key_correct` (every keyed option is right and no distractor is actually true, whether per the transcript or plainly in general). `faithful` means all checks pass. `speaker_slip` is tracked separately: an item that faithfully repeats a misspoken fact is flagged, not failed.
- **Reason before verdict:** the judge writes its reasoning before the booleans. With the verdict first, the flags contradicted their own reasons.
- **Stages:** rates are reported for `raw` (all candidates), `rejected` (what the pipeline's own LLM validation dropped), and `kept` (what a user sees). This measures what validation actually buys.
- **Noise, and the multiple-runs rule:** there are ~30 items per group, and generation is stochastic (fresh items every run), so one item moves a rate by ~0.03. *Identical* code scored 0.71 and 0.87 on quiz key correctness in two runs, so treat single-run differences under ~0.15 as noise. **Run every variant at least twice before drawing a conclusion.** A single run once made the flashcard validator look fixed when it wasn't (see the README).

### Chat answers

`python -m app.eval.chat [--label X]` sends every golden question through the production `answer_question`, with no conversation history. gpt-4o then judges each answer against **the sources that call returned**: the reranked chunks on the specific path, the topic summaries on the broad path.

- **Checks:** for specific and broad questions, `supported` (every factual claim is in the sources) and `answers_question` (it answers what was asked rather than declining or dodging). For out-of-scope questions, `declines` (it plainly says the video doesn't cover this) and `supported` (it doesn't answer anyway from general knowledge). `speaker_slip` is flagged, not failed, as in the faithfulness eval. The results also record the answer model's own `grounded` flag, and which path each question was routed to (`routed_broad`).
- **Why judge against the returned sources, not the whole transcript:** this isolates the answer step. Whether the right sources came back is the retrieval eval's job, so a retrieval miss doesn't show up here as a hallucination.
- **The blind spot that follows:** the judge can't see what the sources left out. A broad question routed to the specific path gets a 5-chunk answer that the judge scores as complete. `routed_broad` is the metric for that failure, not `answers_question`.
- **Slip detection is unreliable here.** Chat repeated a known slip as fact in both committed runs, and the judge flagged it in neither. Treat `speaker_slips` as a floor, not a count.

### Segmentation

Segmentation is not scored automatically. Boundaries are reviewed by hand, and that is a limitation. Reviewing the three eval videos found that auto-captioned videos collapsed into a few huge segments: a 3-hour podcast became 4 segments and a 10-minute tutorial became 1, because punctuation-free captions defeated sentence grouping ([#15](https://github.com/jdavidIP/grasp/issues/15), fixed in §2). The golden set survived the fix unchanged because it scores timestamps, which let both evals measure the change directly: faithfulness of shipped items rose (flashcards 0.81 → 0.86, quizzes 0.80 → 0.86), and retrieval hit@1 dipped (0.88 → 0.81) because every chunk boundary moved.

### Rate limits

gpt-4o calls in the eval tools run sequentially. Running them in parallel exceeds the account's tokens-per-minute limit.
