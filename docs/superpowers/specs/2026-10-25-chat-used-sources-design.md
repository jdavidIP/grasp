# Chat used sources — design

For [#47](https://github.com/jdavidIP/grasp/issues/47). Replaces the inline-citation design (`2026-10-24-chat-inline-citations-design.md`, removed from the tree; read it at commit `2d9847b`), which was dropped after calibration; see "Why not inline markers".

## Why

The user checks chat answers against the video: open the source list, click a source, the player jumps there, confirm the video says it. Specific answers always list 5 sources. `rerank` keeps the top `RERANK_KEEP = 5` chunks with no relevance cut and the UI lists all of them, but the answer often rests on one or two and the bottom ones can be unrelated. That costs clicks and can make a correct answer look unsupported.

## Goals

1. A specific answer lists **only the excerpts the answer used**, not all 5 it was shown.
2. **No source means not verified:** a specific answer the model calls grounded but that names no excerpt is shown with the "Not covered in this video" tag.
3. The used sources survive a reload.

## Non-goals

- Inline `[n]` markers in the answer text (see below).
- Sources for broad answers. They stay as today: the topic list is their navigation.
- Changing what retrieval feeds the answer model (the rerank cut is a separate retrieval change, measured against the retrieval eval).
- Any change to flashcard or quiz behaviour.
- Back-filling answers already in the history.

## Anti-goals (fails even if it works)

- Dropping the excerpt that actually states the answer, leaving the user nothing to check against.
- A drop in chat-eval grounding (`supported`, `answers_question`) or in out-of-scope declines.
- Correct answers tagged "Not covered" often enough to matter.

## Why not inline markers

The first design had the model mark each sentence with `[n]` and the app keep a marker only if the claim's embedding was similar enough to the chunk. Calibration on 168 (claim, chunk) pairs from two golden-set runs, labelled by gpt-4o and spot-checked by hand (10 of 11 labels agreed), showed it can't work:

| Path | Pairs | Supported | Cutoff for target precision | Supported markers kept |
|---|---|---|---|---|
| Specific (90%) | 91 | 44 (48%) | 0.725 | 2 of 44 |
| Broad (80%) | 77 | 17 (22%) | 0.593 | 4 of 17 |

- Similarity measures "same subject", not "said here": most unsupported markers pointed at the right moment while their sentence added something that moment doesn't say (Gorbachev, "Austria and Belgium"), so they scored as high as supported ones.
- Broad sentences are often lists ("covers variables, loops and functions") that no single timestamp backs.
- A gpt-4o-mini support check could replace the similarity cut (+~0.8 s per answer, measured), but most markers would still be dropped, so it would buy little for a lot of moving parts. Spoken transcripts make sentence-level citation weak: facts ramble across chunk boundaries and paraphrase loosely.

The labelled pairs are kept in `api/eval/results/citation-*-2026-10-25-*.json` as the record of this decision.

## How it works

### 1. The model says which excerpts it used

`SPECIFIC_SYSTEM_PROMPT` (`app/prompts/chat_answer.py`) gets a fourth JSON key, `"used_excerpts"`: the numbers of the excerpts the answer relies on; empty when `"grounded"` is false. Excerpts are already numbered `[0]…[k]` in the user prompt. Exact wording is the builder's; the chat eval grades it.

### 2. The app filters the sources

In `_answer_specific`, after generation:

- Keep the entries of `used_excerpts` that are ints in range, without duplicates.
- `sources` = those reranked chunks, **in rerank order** (most relevant first), not the model's order. (My call: stable and already meaningful.)
- **Missing or malformed key** (absent, not a list): fall back to all 5 sources, as today. (My call: a format slip shouldn't tag a correct answer "Not covered". The eval counts how often this happens.)
- An explicit empty list from a grounded answer means no source.
- `grounded` = the model's `grounded` **and** at least one source. The model's own flag is kept for the eval.
- When that rule flips an answer to ungrounded, its `slips` are emptied too, so the API matches the UI, which hides slips under "Not covered".
- A model-ungrounded answer has no sources, as today.

### 3. Storage, history, UI

No change. The router already stores `cited_chunk_ids` from the returned sources, `load_history` rebuilds them in stored order, and `ChatPanel` lists whatever sources it gets. Old rows keep their 5 sources.

### 4. Measuring it

In this order, cheapest first:

1. **Source-span check (no judge, computed in the chat eval run):** for specific golden questions with a span, whether the used sources still overlap the golden span, compared with the 5 retrieved. Reports, among questions whose 5 overlapped the span, the share whose used sources still do.
2. **Chat eval ≥2 runs** (`python -m app.eval.chat`). Baseline: the 2026-10-22 `48-question-first` runs (chat code is unchanged since). Report:
   - the existing checks (`supported`, `answers_question`, `declines`);
   - `flipped`: answers turned "Not covered" by the no-source rule, split by kind. On out-of-scope questions they are catches; on specific questions the judge says are supported they are **false alarms**;
   - sources per answer (expected well under 5) and how often the fallback fired.

**Pass criteria**, per run:

- **No grounding regression:** `supported`, `answers_question` and `declines` don't drop by more than the spread between the two baseline runs.
- **False alarms ≤ 2 of the 40 answerable questions** (about 5%, the user's limit).
- **Span kept in ≥ 90%** of the questions whose 5 retrieved sources overlapped the span (my call on the number).
- Above any limit: report to the user. Don't tune the prompt to pass the eval.

Eval comparability:

- **The judge keeps seeing what the model saw**, not the used sources: `answer_question` also returns `context` (the 5 reranked chunks, or every segment summary), and the eval judges against it. Otherwise narrower sources would lower `supported` for reasons unrelated to answer quality.
- Records keep both the model's `grounded` and the final one.

Faithfulness eval: not run; flashcard and quiz behaviour doesn't change.

Rough eval cost: about $0.25 per chat run, so about $0.50 for two runs.

### 5. Docs

- `docs/ARCHITECTURE.md`: specific answers list the excerpts the model says it used; the grounded rule; why not inline markers (short, pointing here).
- `docs/API.md`: `sources` for a specific answer is the used excerpts, in rerank order.
- README evaluation section: the results and the inline-marker calibration finding.

## What carries over from the inline-marker branch

Kept: the eval judging against `context`, and the `model_grounded` / `flipped` / `false_alarms` counts. Everything else (marker prompts, marker parsing and renumbering, broad chunk matching, the shared nearest-chunk helper, the citation CLI and judge prompt, the broad history change) is removed. How to get there on the branch is the builder's call.

## Left to the builder

- Exact prompt wording (graded by the eval).
- Commit split (one concern per commit, per `CLAUDE_WORKFLOW.md`).
