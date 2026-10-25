# Chat Inline Citations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chat answers carry inline `[n]` markers that seek the player, and list only the sources those markers cite, each one cleared by a calibrated relevance threshold.

**Architecture:** The answer model marks each claim with the excerpt (specific) or topic (broad) it relies on. A pure module (`app/generation/citations.py`) parses claims and renumbers markers; `chat.py` resolves each marker to a chunk (broad: nearest chunk in the topic by embedding, shared with `item_source_spans`), drops markers below the path's threshold, and sets `grounded` false when none survive. Storage reuses `cited_chunk_ids` for both scopes; the UI turns `[n]` into seek buttons.

**Tech Stack:** FastAPI, SQLAlchemy 2, pgvector, OpenAI (`gpt-4o-mini`, `text-embedding-3-small`, `gpt-4o` judge), React + TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-24-chat-inline-citations-design.md`

## Global Constraints

- Branch `feat/47-chat-inline-citations`. **Every commit pauses for the user's review** (`CLAUDE_WORKFLOW.md`); no `Co-Authored-By` trailer; commit messages end with `Refs #47`.
- Prompts live in `app/prompts/`; every LLM call goes through `app/generation/llm.py`.
- Thresholds: lowest cutoff with surviving-marker precision **≥ 0.90 (specific)** and **≥ 0.80 (broad)**. Stop and ask the user if, at that cutoff, recall of supporting pairs is **< 0.70**.
- **Thresholds are set once from labelled pairs and never tuned to make the chat eval pass.**
- Chat eval pass: no drop in `supported` / `answers_question` / `declines` beyond the spread between the 2026-10-22 `48-question-first` run1/run2; **false alarms ≤ 2 of 40 answerable questions per run**. Above either: report to the user.
- No faithfulness eval; flashcard/quiz behaviour must not change (`item_source_spans` tests unchanged and passing).
- Tests share the dev DB: only create/delete `test-%` videos. Backend tests: `docker compose exec api pytest`; frontend: `docker compose exec web npm test` and `npm run typecheck`.
- Tell the user the expected cost before any batch of judged runs (calibration labels ~$0.10; chat eval ~$0.25/run).

## Review Focus

1. **Marker placed after the period** (`…in 1488. [2]`): the claim is the sentence before it, not the next one. → Task 1 test `test_claims_marker_after_period_belongs_to_previous_sentence`.
2. **A bracketed number that isn't a citation or is out of range** (`[7]` with 5 excerpts, `[1990]`): removed from the answer, never a source. → Task 4 test `test_specific_drops_out_of_range_markers`; Task 8 test `renders an out-of-range bracket as plain text`.
3. **The same chunk cited by two sentences**: one source, one number used twice. → Task 1 test `test_renumber_reuses_number_for_repeated_chunk`.
4. **Grounded answer whose markers all fall below the threshold**: `grounded` false, `sources` and `slips` empty, text kept. → Task 4 test `test_grounded_answer_with_no_surviving_marker_becomes_not_covered`.
5. **Broad topic with no embedded chunks**: its markers are dropped, no crash. → Task 2 test `test_nearest_chunks_returns_none_for_a_segment_without_chunks`.

---

### Task 1: Citation parsing and renumbering (pure)

**Files:**
- Create: `api/app/generation/citations.py`
- Test: `api/tests/test_citations.py`

**Interfaces:**
- Produces:
  - `MARKER_RE = re.compile(r"\[(\d+)\]")`
  - `strip_markers(text: str) -> str` — removes every `[n]` and the whitespace directly before it.
  - `claims(answer: str) -> list[tuple[int, str]]` — one `(model_index, claim_text)` per marker occurrence, in text order.
  - `renumber(answer: str, kept: list[uuid.UUID | None]) -> tuple[str, list[uuid.UUID]]` — `kept[i]` is the chunk for the i-th marker occurrence, or `None` to drop it. Returns the text with surviving markers as `[1]…[m]` in first-appearance order and the m chunk ids in that order.
  - `citation_problems(answer: str, n_sources: int, grounded: bool) -> list[str]` — validity check used by tests and the eval: every marker in `1…n_sources`, every source number used at least once, `grounded` ⇒ `n_sources ≥ 1`, not `grounded` ⇒ no markers and no sources. Empty list means valid.

Claim text algorithm (not determined by the signature):
```
for each maximal run of adjacent markers (only whitespace between them):
    end = start of the run
    body = answer[:end].rstrip()
    if body ends with . ! or ?: body = body[:-1]      # marker placed after the period
    start = position after the last sentence boundary in body
            (boundary = [.!?] followed by whitespace, or a newline), else 0
    claim = strip_markers(body[start:]).strip()
    every marker in the run gets this claim
```

- [ ] **Step 1: Write the failing tests**

```python
def test_claims_one_per_marker_in_order():
    assert claims("Homer wrote it [0]. It is about Odysseus [2][1].") == [
        (0, "Homer wrote it"),
        (2, "It is about Odysseus"),
        (1, "It is about Odysseus"),
    ]

def test_claims_marker_after_period_belongs_to_previous_sentence():
    assert claims("Columbus sailed in 1492. [3] Then he returned.") == [(3, "Columbus sailed in 1492")]

def test_claims_newline_is_a_boundary():
    assert claims("Intro line\nLists use brackets [1]") == [(1, "Lists use brackets")]

def test_strip_markers():
    assert strip_markers("A [0]. B [1][2].") == "A. B."

def test_renumber_drops_and_numbers_by_first_appearance():
    a, b = uuid.uuid4(), uuid.uuid4()
    text, ids = renumber("X [4]. Y [0]. Z [2].", [b, None, a])
    assert text == "X [1]. Y. Z [2]."
    assert ids == [b, a]

def test_renumber_reuses_number_for_repeated_chunk():
    a = uuid.uuid4()
    text, ids = renumber("X [0]. Y [3].", [a, a])
    assert text == "X [1]. Y [1]."
    assert ids == [a]

def test_renumber_dedupes_a_run_that_maps_to_one_chunk():
    a = uuid.uuid4()
    assert renumber("X [0][1].", [a, a]) == ("X [1].", [a])

def test_citation_problems():
    assert citation_problems("A [1]. B [2].", 2, True) == []
    assert citation_problems("A [3].", 2, True)            # out of range
    assert citation_problems("A [1].", 2, True)            # source 2 never cited
    assert citation_problems("A.", 0, True)                # grounded with no source
    assert citation_problems("A [1].", 1, False)           # ungrounded with a marker
```

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose exec api pytest tests/test_citations.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement the four functions in `api/app/generation/citations.py`**

- [ ] **Step 4: Run to verify they pass** — same command, all PASS; `docker compose exec api ruff check .` clean.

- [ ] **Step 5: Show the user, wait for approval, commit** — `feat: parse and renumber chat citation markers`

---

### Task 2: Shared nearest-chunk helper

**Files:**
- Modify: `api/app/generation/common.py:155-185` (`item_source_spans`)
- Test: `api/tests/test_generation_common.py`

**Interfaces:**
- Produces: `async def nearest_chunks(session: AsyncSession, segment_ids: list[uuid.UUID], embeddings: list[list[float]]) -> list[tuple[TranscriptChunk, float] | None]` — for each `(segment_ids[i], embeddings[i])`, the embedded chunk of that segment with the highest `cosine_similarity` and that similarity; `None` when the segment has no embedded chunks. One query for all segments; no embedding call (callers embed).
- `item_source_spans` keeps its signature and results; it now embeds its items and calls `nearest_chunks`, falling back to the segment span on `None`.

- [ ] **Step 1: Write the failing tests** (DB-backed, `test-%` video like the existing `item_source_spans` tests)

```python
async def test_nearest_chunks_picks_most_similar_chunk_with_its_score(...):
    # segment with chunks embedded _embedding(0) and _embedding(1); query _embedding(1)
    [(chunk, score)] = await common.nearest_chunks(session, [segment.id], [_embedding(1)])
    assert chunk.id == second_chunk.id
    assert score == pytest.approx(1.0)

async def test_nearest_chunks_returns_none_for_a_segment_without_chunks(...):
    assert await common.nearest_chunks(session, [empty_segment.id], [_embedding(0)]) == [None]
```

- [ ] **Step 2: Run to verify they fail** — `docker compose exec api pytest tests/test_generation_common.py -v`; the two new tests FAIL, existing ones pass.

- [ ] **Step 3: Implement `nearest_chunks`; rewrite `item_source_spans` on top of it.**

- [ ] **Step 4: Run** — whole file PASS (existing `item_source_spans` tests unchanged).

- [ ] **Step 5: Show the user, wait for approval, commit** — `refactor: share nearest-chunk matching for citations`

---

### Task 3: Answer prompts ask for markers; history drops them

**Files:**
- Modify: `api/app/prompts/chat_answer.py`
- Test: `api/tests/test_chat_generation.py`

**Interfaces:**
- Consumes: `strip_markers` (Task 1).
- `build_broad_user_prompt(question, segments: list[tuple[str, str]], history, slips)` unchanged in signature; summaries now render as `[{i}] ({label}) {summary}`.
- `_history_block` applies `strip_markers` to each turn's content.

Prompt requirements (wording is the builder's; the eval grades it):
- **Both prompts:** end each sentence that states something from the video with the bracketed number of the source it relies on (`[2]`, or `[1][3]` for two); no marker on sentences that state nothing from the video; numbers only from the given list; when `"grounded"` is false, no markers.
- **Specific:** the numbers are the excerpt numbers.
- **Broad:** the numbers are the topic numbers.

- [ ] **Step 1: Write the failing tests**

```python
def test_broad_prompt_numbers_the_topics():
    prompt = build_broad_user_prompt("q", [("Intro", "A."), ("Body", "B.")], [], [])
    assert "[0] (Intro) A." in prompt and "[1] (Body) B." in prompt

def test_history_is_passed_without_citation_markers():
    history = [{"role": "assistant", "content": "Homer wrote it [1]."}]
    prompt = build_specific_user_prompt("q", ["x"], history, [])
    assert "Homer wrote it." in prompt and "[1]" not in prompt.split("Current question")[0]

def test_both_system_prompts_ask_for_markers():
    for p in (SPECIFIC_SYSTEM_PROMPT, BROAD_SYSTEM_PROMPT):
        assert "[1][3]" in p
```

- [ ] **Step 2: Run to verify they fail** — `docker compose exec api pytest tests/test_chat_generation.py -v`

- [ ] **Step 3: Update the prompts and builders.**

- [ ] **Step 4: Run** — file PASS.

- [ ] **Step 5: Show the user, wait for approval, commit** — `feat: ask the chat model to mark each claim's source`

---

### Task 4: Resolve markers in both answer paths

**Files:**
- Modify: `api/app/generation/chat.py` (`_answer_specific`, `_answer_broad`, `answer_question` docstring)
- Test: `api/tests/test_chat_generation.py`

**Interfaces:**
- Consumes: `claims`, `renumber` (Task 1); `nearest_chunks` (Task 2); `llm.embed_texts`.
- Produces (in `chat.py`):
  - `SPECIFIC_CITATION_MIN_SIMILARITY: float = 0.0` and `BROAD_CITATION_MIN_SIMILARITY: float = 0.0` — placeholders that keep every resolved marker until Task 7 sets the calibrated values. Read at call time (`chat.SPECIFIC_…`) so the calibration script can leave them at 0.
  - `answer_question` result gains `"context": list[dict]` (what the model saw: `_chunk_source` per reranked chunk, or `_segment_source` per segment) and `"model_grounded": bool`. `"sources"` becomes the cited chunks only, as `_chunk_source` dicts in marker order. `"answer"` is the renumbered text.
  - Each result also carries `"citations": list[dict]` — one per marker occurrence: `{"path", "claim", "chunk_id", "chunk_text", "similarity", "kept"}`; `chunk_id`/`chunk_text`/`similarity` are `None` when no chunk was found. Used by Task 6; dropped by the API.
- Rules: specific candidate = `top_chunks[model_index]` (out of range ⇒ dropped); broad candidate = `nearest_chunks` over `segments[model_index]` (out of range or `None` ⇒ dropped). Keep iff `similarity ≥` the path's threshold. All claim texts embedded in one `embed_texts` call (skip the call when there are no markers). Model `grounded` false ⇒ all markers dropped. Final `grounded = model_grounded and len(sources) ≥ 1`; final ungrounded ⇒ `slips = []`.

- [ ] **Step 1: Write the failing tests** (mock `llm.generate_json` and `llm.embed_texts`; patch thresholds with `monkeypatch.setattr(chat, "SPECIFIC_CITATION_MIN_SIMILARITY", 0.5)`)

```python
async def test_specific_keeps_only_cited_chunks_above_threshold(monkeypatch):
    # 3 reranked chunks; answer "A [2]. B [0]."; claim A embeds close to chunk 2, B far from chunk 0
    result = await chat._answer_specific(...)
    assert result["answer"] == "A [1]. B."
    assert [s["chunk_id"] for s in result["sources"]] == [chunks[2].id]
    assert len(result["context"]) == 3
    assert result["grounded"] is True and result["model_grounded"] is True

async def test_specific_drops_out_of_range_markers(monkeypatch):
    # answer "A [7]." with 5 chunks -> "A.", no sources, grounded False (no source survived)

async def test_grounded_answer_with_no_surviving_marker_becomes_not_covered(monkeypatch):
    # model grounded True, slips_used [0], every similarity below threshold
    assert result["grounded"] is False and result["model_grounded"] is True
    assert result["sources"] == [] and result["slips"] == []

async def test_ungrounded_answer_has_markers_stripped_and_skips_embedding(monkeypatch):
    # model grounded False, answer "Not covered [1]." -> "Not covered.", embed_texts not called

async def test_broad_cites_the_nearest_chunk_in_the_marked_topic(monkeypatch):
    # DB-backed test- video: 2 segments with embedded chunks; answer "Intro claim [0]. Body claim [1]."
    # embed_texts returns vectors matching one chunk per segment
    assert [s["chunk_id"] for s in result["sources"]] == [intro_chunk.id, body_chunk.id]
    assert all(s["chunk_id"] is not None for s in result["sources"])
    assert len(result["context"]) == 2   # segment summaries the model saw
```

Update `test_answer_broad_path_uses_segment_summaries` and `test_answer_specific_happy_path` to the new result shape (sources = cited chunks; context = what the model saw).

- [ ] **Step 2: Run to verify they fail** — `docker compose exec api pytest tests/test_chat_generation.py -v`

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run** — file PASS; full `docker compose exec api pytest` PASS except `tests/test_chat.py` cases Task 5 updates.

- [ ] **Step 5: Show the user, wait for approval, commit** — `feat: resolve chat citation markers to chunks above a threshold`

---

### Task 5: Persist and rebuild cited sources for both scopes

**Files:**
- Modify: `api/app/routers/chat.py`, `api/app/generation/chat.py` (`load_history`), `api/app/schemas/chat.py`, `web/src/types/chat.ts`
- Test: `api/tests/test_chat.py`

**Interfaces:**
- Router stores `content = result["answer"]` (renumbered) and `cited_chunk_ids = [s["chunk_id"] for s in result["sources"]] or None` for both scopes; `ChatResponse(**result)` ignores the extra keys.
- `load_history`: `sources` rebuilt from `cited_chunk_ids` in stored order for both scopes; the broad all-segments branch is removed.
- `ChatSource.chunk_id: uuid.UUID` (non-null); `web/src/types/chat.ts` `chunk_id: string`.

- [ ] **Step 1: Update/replace tests**
  - Replace `test_chat_broad_sources_store_null_cited_chunk_ids` with `test_chat_broad_answer_stores_its_cited_chunk_ids` (broad fake answer with two chunk sources → `cited_chunk_ids == [ids…]`, `scope == "broad"`).
  - Replace `test_history_lists_every_segment_for_a_broad_answer` with `test_history_rebuilds_broad_sources_from_cited_chunks`.
  - Add `test_history_shows_no_sources_for_an_old_broad_answer` (row with `scope="broad"`, `cited_chunk_ids=None` → `sources == []`).
  - Add `test_chat_stores_the_renumbered_answer` (fake answer `"A [1]."` → stored `content == "A [1]."`).

- [ ] **Step 2: Run to verify they fail** — `docker compose exec api pytest tests/test_chat.py -v`

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run** — full `docker compose exec api pytest` PASS; `docker compose exec api alembic check` reports no changes; `docker compose exec web npm run typecheck` clean.

- [ ] **Step 5: Show the user, wait for approval, commit** — `feat: store and rebuild cited chat sources for both scopes`

---

### Task 6: Eval support — comparable judging, validity check, calibration tooling

**Files:**
- Modify: `api/app/eval/chat.py`
- Create: `api/app/eval/citations.py`, `api/app/prompts/citation_judge.py`
- Test: `api/tests/test_eval.py`

**Interfaces:**
- Consumes: Task 4's `context`, `model_grounded`, `citations`; Task 1's `strip_markers`, `citation_problems`.
- `eval/chat.py`: `_judge` builds its prompt from `answer["context"]` and `strip_markers(with_slip_notes(...))`. Records add `model_grounded`, `n_sources`, `n_markers`. `summarize` adds per kind `flipped` (count of `model_grounded and not grounded`) and, for specific/broad, `false_alarms` (flipped and judged `supported`).
- `eval/citations.py` — `python -m app.eval.citations {validity|collect|label|pick} [--label X]`:
  - `validity`: runs the golden set through `answer_question` (thresholds as committed), prints `citation_problems` per answer; exit code 1 if any. No judge.
  - `collect`: runs the golden set with both thresholds forced to 0.0, writes every `citations` entry with a chunk to `api/eval/results/citation-pairs-<date>.json`.
  - `label`: gpt-4o (`llm.EVAL_MODEL`, sequential) labels each pair `supports: bool` with `CITATION_JUDGE_SYSTEM_PROMPT`; writes `citation-labels-<date>.json`.
  - `pick`: reads the labels, prints per path the chosen cutoff, precision, recall, n.
  - `pick_cutoff(pairs: list[tuple[float, bool]], target_precision: float) -> tuple[float, float, float] | None` — lowest observed similarity t where precision of pairs with similarity ≥ t is ≥ target; returns `(t, precision, recall)`, `None` if no t reaches it.

- [ ] **Step 1: Write the failing tests**

```python
def test_pick_cutoff_takes_the_lowest_threshold_reaching_the_target():
    pairs = [(0.2, False), (0.3, True), (0.35, False), (0.4, True), (0.5, True)]
    assert pick_cutoff(pairs, 0.9) == (0.4, 1.0, pytest.approx(2 / 3))

def test_pick_cutoff_none_when_unreachable():
    assert pick_cutoff([(0.5, False), (0.6, False)], 0.8) is None

def test_summarize_counts_flips_and_false_alarms():
    # one specific record model_grounded True, grounded False, judged supported -> flipped 1, false_alarms 1
```

- [ ] **Step 2: Run to verify they fail** — `docker compose exec api pytest tests/test_eval.py -v`

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run** — full suite PASS, ruff clean.

- [ ] **Step 5: Show the user, wait for approval, commit** — `feat: citation calibration tooling and comparable chat judging`

---

### Task 7: Calibrate the thresholds (data task)

**Files:**
- Modify: `api/app/generation/chat.py` (the two threshold constants, with a comment citing the labels file)
- Create: `api/eval/results/citation-pairs-<date>.json`, `citation-labels-<date>.json`
- Modify: `README.md` (evaluation section: how the cutoffs were chosen)

- [ ] **Step 1: Validity check** — `docker compose restart api`, then `MSYS_NO_PATHCONV=1 docker compose exec api python -m app.eval.citations validity`. Expected: exit 0. Costs only gpt-4o-mini.
- [ ] **Step 2: Collect pairs** — `python -m app.eval.citations collect`.
- [ ] **Step 3: Tell the user the label cost (~$0.10), then label** — `python -m app.eval.citations label`. Hand-check ~20 labels; note disagreements in the commit message.
- [ ] **Step 4: Pick** — `python -m app.eval.citations pick` with targets 0.90 (specific), 0.80 (broad). **If either path returns `None` or recall < 0.70: stop and report to the user.**
- [ ] **Step 5: Set the constants; rerun validity** (exit 0) and the backend suite.
- [ ] **Step 6: Show the user the numbers, wait for approval, commit** — `feat: set calibrated chat citation thresholds`

---

### Task 8: Markers in the chat UI

**Files:**
- Create: `web/src/lib/citations.ts`, `web/src/lib/citations.test.ts`
- Modify: `web/src/components/ChatPanel.tsx`, `web/src/components/ChatPanel.css`, `web/src/components/ChatPanel.test.tsx`

**Interfaces:**
- Produces: `splitCitations(content: string, sourceCount: number): Array<string | number>` — text pieces and 1-based source numbers; `[n]` with `1 ≤ n ≤ sourceCount` becomes `n`, anything else stays text.
- `AssistantMessage` renders numbers as `<button className="chat-cite">` with `aria-label={\`Source ${n}, ${formatTime(start)}\`}` calling `onSeek(sources[n-1].start_time)`; styles per handoff §4 (`vertical-align: super`, 11px tabular, `var(--color-accent-700)`, no border/background; hover `var(--color-accent)` + underline). The `chunk_id !== null` filter is removed.

- [ ] **Step 1: Write the failing tests**

```ts
it('splits markers in range and leaves others as text', () => {
  expect(splitCitations('A [1]. B [3].', 2)).toEqual(['A ', 1, '. B [3].'])
})
```
ChatPanel.test.tsx:
- `it('renders citation markers that seek to their source')` — reloaded answer `"Homer wrote it [1]."` with one source at 83s → button "Source 1, 1:23" click calls `onSeek(83)`.
- `it('renders an out-of-range bracket as plain text')` — `"Year [5]."` with one source → no `Source 5` button, text contains `[5]`.
- Replace `lists no sources for a broad answer…` with `lists a broad answer's cited sources`.

- [ ] **Step 2: Run to verify they fail** — `docker compose exec web npm test`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — `npm test` PASS, `npm run typecheck` clean, `npm run lint` clean; `docker compose restart web`, check one specific and one broad answer in Chrome (markers seek, list matches).
- [ ] **Step 5: Show the user, wait for approval, commit** — `feat: inline citation markers in chat answers`

---

### Task 9: Chat eval runs and docs

**Files:**
- Create: `api/eval/results/chat-<date>-citations-run1.json`, `-run2.json`
- Modify: `README.md`, `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, `docs/API.md`

- [ ] **Step 1: Tell the user the cost (~$0.50), then run twice** — `python -m app.eval.chat --label citations-run1`, then `-run2`.
- [ ] **Step 2: Check the pass criteria** against the 2026-10-22 `48-question-first` runs (Global Constraints). **Above either limit: stop and report; don't change thresholds.**
- [ ] **Step 3: Docs** — ARCHITECTURE: chat answer flow (markers, resolution, thresholds, no-source ⇒ not covered) and the after-the-fact-matching tradeoff for broad answers. DATA_MODEL: `content`/`cited_chunk_ids` for both scopes. API: `sources` cited-only, ordered to match `[n]`. README: results, sources per answer, flips/false alarms, the #41-style catches.
- [ ] **Step 4: Show the user, wait for approval, commit** — `docs: record #47 citation results`
- [ ] **Step 5:** code-reviewer agent on the branch diff; PR only on the user's request (`Closes #47`).
