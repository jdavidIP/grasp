# Chat inline citations — design

For [#47](https://github.com/jdavidIP/grasp/issues/47). Visual reference: handoff §4 "Citation markers" (`docs/design/README.md`).

## Why

The user checks chat answers against the video: read a claim, click its source, the player jumps there, confirm the video says it. Today that fails two ways:

- **Specific answers always list 5 sources.** `rerank` keeps the top `RERANK_KEEP = 5` chunks with no relevance cut, and the UI lists all of them. The answer often rests on one; the bottom ones can be unrelated, which costs clicks and can make a correct answer look unsupported.
- **Broad answers list nothing.** Their sources are whole segments, which the UI hides (the topic list already shows them). A summary like "the Odyssey is a poem by Homer about Odysseus' journey home to Ithaca" makes several checkable claims, each of which a specific question would have sourced.

The user checks **sentence by sentence**, so each claim needs its own marker pointing at the moment that backs it.

## Goals

1. Answer prose carries inline markers `[1]`, `[2]`… that seek the player, styled per handoff §4.
2. The source list under an answer shows **only sources a marker points to**, numbered to match the markers.
3. **Both paths cite transcript chunks.** Broad answers point at specific moments, not topic starts.
4. **Every marker clears a relevance threshold.** A marker that is merely the nearest match is dropped; a claim with no source above the threshold shows no marker.
5. **No source means not verified:** an answer the model calls grounded but with no marker left after the threshold is shown with the "Not covered in this video" tag.
6. Markers and cited sources survive a reload.

## Non-goals

- Changing what retrieval feeds the answer model (the rerank cut is a separate retrieval change, measured against the retrieval eval).
- Changing how broad answers are composed: they are still written from segment summaries.
- Any change to flashcard or quiz behaviour.
- Back-filling markers into answers already in the history.

## Anti-goals (fails even if it works)

- A marker that points at an excerpt not backing its sentence. Worse than no marker: the user checks the wrong spot and may distrust a correct answer.
- A drop in chat-eval grounding (`supported`, `answers_question`) or in out-of-scope declines.
- Correct answers tagged "Not covered" often enough to matter. The eval must count this cost, not only the false-grounded answers the rule catches.

## How it works

### 1. The model marks its claims

- **Specific prompt** (`app/prompts/chat_answer.py`): the excerpts are already numbered `[0]…[k]`. The model ends each claim with the number of the excerpt it relies on, e.g. `… in 1488 [2].` A claim relying on two excerpts gets two markers `[1][3]`. Sentences that make no claim about the video carry none.
- **Broad prompt:** the summaries get numbers too (`[0] (label) summary`, replacing today's `[label] summary`), and the model marks each claim with the number of the topic it came from.
- Ungrounded answers carry no markers; any the model writes are stripped.
- Both prompt changes are graded by the chat eval (section 5). Prompts stay in `app/prompts/`.

### 2. The app resolves each marker to a chunk and applies the threshold

After generation, for each marker:

- **Claim text** = the text of the sentence the marker ends, without markers. A sentence is the span from the previous sentence end (`.`, `?`, `!` followed by whitespace, or a newline) up to the marker. Several markers on one sentence share the same claim text.
- **Specific:** the candidate chunk is the excerpt the marker names.
- **Broad:** the candidates are the chunks of the topic the marker names; the best one is the chunk whose embedding is most similar to the claim's. This is the same after-the-fact matching flashcards and quiz items use for their spans (#50, `item_source_spans` in `app/generation/common.py`).
- **Threshold:** the marker survives only if cosine similarity between the claim's embedding and the chosen chunk's embedding is ≥ the path's threshold (section 4). Otherwise the marker is removed from the text.
- All claim embeddings for one answer come from **one** `embed_texts` call.
- Out-of-range or malformed markers are removed.

Then:

- Surviving chunks are numbered **1…m in order of first appearance** in the text; the markers are rewritten to those numbers. A chunk cited twice keeps one number.
- `sources` = those m chunks, in that order.
- `grounded` = the model's `grounded` **and** m ≥ 1. The model's own flag is kept for the eval (section 5).
- When that rule flips an answer to ungrounded, its `slips` are emptied too (my call): the UI already hides slips under "Not covered", and this keeps the API consistent with it.

The nearest-chunk logic should be shared with `item_source_spans` rather than copied; `item_source_spans`' results must not change (its existing tests guard that). How to factor it is the builder's call.

### 3. Storage and history

- `chat_messages.content` stores the answer with the renumbered `[1]…[m]` markers. `cited_chunk_ids` stores the m chunk ids in marker order. **No schema change**: broad answers now cite chunks too, so the issue's proposed `cited_segment_ids` is not needed.
- `load_history` rebuilds `sources` from `cited_chunk_ids` for **both** scopes, in stored order. The broad branch that returned every segment goes away.
- Markers are **stripped from history before it goes back into a prompt** (`_history_block`), so the model doesn't copy old numbering into a new answer.
- **Old rows:** a specific answer from before this change has no markers in its text and 5 cited ids, so it keeps showing its 5 sources with no markers. An old broad answer has no cited ids, so it shows none (as today). No migration.
- `ChatSource.chunk_id` can become non-nullable once segment sources are gone (builder's call; the TypeScript type mirrors it).

### 4. Calibrating the threshold

`text-embedding-3-small` similarities for related text sit in a narrow band (often 0.3–0.6), so the threshold must be measured, not guessed.

- Build a labelled set of (claim, chunk) pairs from answers on the eval videos (chat golden-set questions, both paths): supporting pairs and non-supporting ones, including the "nearest but unrelated" case.
- Labels come from the gpt-4o judge model with a short support prompt, and a hand spot-check of a sample (my call; a few cents).
- **The user's rule for picking the cutoff:** favour fewer wrong markers over fewer dropped ones. Per path, take the lowest cutoff at which the surviving markers are correct at least:
  - **90% of the time for specific answers**,
  - **80% of the time for broad answers** (their claims paraphrase summaries, so they match raw chunks less closely).
- So there are two thresholds, `SPECIFIC_CITATION_MIN_SIMILARITY` and `BROAD_CITATION_MIN_SIMILARITY`, each labelled set split by path.
- Commit the labelled set and the chosen values with how they were chosen (`docs/` or the README eval section).
- **Set once from the labels, never tuned to make the chat eval pass.**
- **Stop and ask the user** (my call on the trigger) if, for either path, no cutoff reaches its target while still keeping at least 70% of the supporting pairs.

### 5. Measuring it

In this order, cheapest first:

1. **Citation validity (near-free, no judge):** run the chat path over the golden set; every marker in the stored text is in `1…len(sources)`, every listed source is cited, every source has non-empty text, and no grounded answer has zero sources.
2. **Threshold calibration** (section 4).
3. **Chat eval ≥2 runs** (`python -m app.eval.chat`). Baseline: the 2026-10-22 `48-question-first` runs (chat code is unchanged since). Report:
   - the existing checks (`supported`, `answers_question`, `declines`) — no regression;
   - how many answers flip to "Not covered" because no marker survived, split by kind: on out-of-scope questions those are catches (e.g. the #41 Gorbachev false-grounded case); on specific/broad questions the judge says are supported, they are false alarms;
   - marker counts per answer and sources per answer (expected well under 5 for specific).

**Pass criteria**, per run:

- **No grounding regression:** `supported`, `answers_question` and `declines` don't drop by more than the spread between the two baseline runs (my call on the tolerance).
- **False alarms ≤ 2 of the 40 answerable questions (about 5%, the user's limit):** answers flipped to "Not covered" by the no-source rule that the judge says were supported.
- Above either limit: report to the user. Don't loosen a threshold to pass.

Eval comparability rules:

- **The judge keeps seeing what the model saw**, not the cited sources: `answer_question` returns the full retrieved context (the 5 reranked chunks, or every segment summary) alongside the cited `sources`, and the eval judges against the context. Otherwise narrower sources would lower `supported` for reasons unrelated to answer quality.
- **Markers are stripped from the answer the judge reads**, since its source list is numbered differently.
- The records keep both the model's `grounded` and the final one.

**Faithfulness eval: not run (my call).** The issue asks for it, but flashcard and quiz behaviour doesn't change; the shared nearest-chunk refactor is covered by `item_source_spans`' existing tests.

Rough eval cost: about $0.25 per chat run, so $1–1.50 overall with calibration labels.

### 6. UI (`ChatPanel.tsx`)

- The answer text is parsed for `[n]` where 1 ≤ n ≤ `sources.length`; each becomes a `<button>` per handoff §4 (superscript, 11px tabular, `--color-accent-700`, hover accent + underline) that calls `onSeek(sources[n-1].start_time)`. Any other bracketed text renders as plain text.
- The source list shows `sources` as returned (now only cited ones), numbered 1…m to match the markers. The broad-source filter (`chunk_id !== null`) goes away.
- "Not covered in this video" logic is unchanged: it follows `grounded`, which now includes the no-source rule.
- Accessible name for a marker button: e.g. "Source 2, 1:23" (builder's wording).
- Tests: markers render as buttons and seek; out-of-range brackets stay text; a reloaded history message renders its markers.

### 7. Docs

- `docs/ARCHITECTURE.md`: chat answer flow (markers, resolution, threshold, grounded rule) and the tradeoff of after-the-fact matching for broad answers.
- `docs/DATA_MODEL.md`: what `content` and `cited_chunk_ids` now hold for both scopes.
- `docs/API.md`: `sources` is cited-only and ordered to match the `[n]` markers in `answer`/`content`.
- README evaluation section: results, threshold and how it was chosen.

## Order

The prompt changes (section 1) land before calibration (section 4), since they produce the markers being labelled.

## Left to the builder

- Factoring of the shared nearest-chunk helper.
- Exact prompt wording (graded by the eval).
- Commit split (one concern per commit, per `CLAUDE_WORKFLOW.md`).
- Marker accessible-name wording.
