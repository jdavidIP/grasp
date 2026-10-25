# Chat Used Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Specific chat answers list only the excerpts the model says it used; a grounded answer naming none shows "Not covered".

**Architecture:** The specific answer prompt gains a `used_excerpts` JSON key; `_answer_specific` filters the reranked chunks to it and applies the no-source grounded rule. `answer_question` also returns `context` (what the model saw) and `model_grounded` so the chat eval keeps judging against the same material and can count flips and whether the used sources still cover the golden span.

**Tech Stack:** FastAPI, SQLAlchemy async, pytest; OpenAI via `app/generation/llm.py`.

**Spec:** `docs/superpowers/specs/2026-10-25-chat-used-sources-design.md`

## Global Constraints

- Process (`CLAUDE_WORKFLOW.md`): each commit is shown to the user and waits for approval; no Co-Authored-By trailer; no push or PR without an explicit request; `code-reviewer` agent on the branch diff before the PR.
- Prompts live in `app/prompts/`; every LLM call goes through `app/generation/llm.py`.
- Broad answers, storage, history and the UI do not change.
- Tests: `docker compose exec api pytest`; lint: `docker compose exec api ruff check . && docker compose exec api ruff format .`.
- Evals: ≥2 runs per variant; never tune the prompt to pass the eval; tell the user the cost before a judged run (~$0.25 per chat run).

## Review Focus

1. `used_excerpts` containing `True`/`False`: Python bools are ints; they must not select excerpts 1/0 (`type(i) is int`, as `_slips_used` does).
2. Model `grounded: false` with a non-empty `used_excerpts`: no sources, still ungrounded.
3. A list whose entries are all invalid (strings, out of range): treated as an explicit empty list, so a grounded answer becomes "Not covered" (only a missing key or a non-list falls back).
4. Fewer than 5 reranked chunks (`len(candidates) <= RERANK_KEEP`): range check is against `len(top_chunks)`, not 5.
5. Duplicates in `used_excerpts` (`[2, 2]`): one source.

---

### Task 1: Specific answers list only the excerpts they used

**Files:**
- Modify: `api/app/prompts/chat_answer.py` (`SPECIFIC_SYSTEM_PROMPT`)
- Modify: `api/app/generation/chat.py` (`answer_question` docstring, `_answer_specific`, `_answer_broad`)
- Test: `api/tests/test_chat_generation.py`

**Interfaces:**
- Produces: `answer_question` result keys `answer`, `sources`, `grounded`, `slips`, `path` (unchanged meaning except `sources`/`grounded` on the specific path), plus `context: list[dict]` (specific: `_chunk_source` per reranked chunk; broad: the segment sources, same as `sources`; early returns: `[]`), `model_grounded: bool`, and `sources_fallback: bool` (True when `used_excerpts` was missing or not a list and all reranked chunks were returned). The API drops the extra keys (`ChatResponse(**result)` ignores them).
- Rules: valid entries are `type(i) is int and 0 <= i < len(top_chunks)`, deduplicated; `sources` = those chunks in rerank order; model ungrounded ⇒ `sources = []`; final `grounded = model_grounded and bool(sources)`; final ungrounded ⇒ `slips = []`.

- [ ] **Step 1: Write the failing tests** (mock `embed_texts`, `hybrid_search`, `rerank`, `generate_json` as the existing specific tests do; 3 reranked chunks unless stated)

```python
async def test_specific_lists_only_used_excerpts_in_rerank_order(...):
    # model: grounded True, used_excerpts [2, 0, 2, True, "1", 9]
    assert [s["chunk_id"] for s in result["sources"]] == [chunks[0].id, chunks[2].id]
    assert len(result["context"]) == 3
    assert result["grounded"] is True and result["model_grounded"] is True
    assert result["sources_fallback"] is False

async def test_grounded_answer_using_no_excerpt_becomes_not_covered(...):
    # model: grounded True, used_excerpts ["x"], slips_used [0] (a slip in the chunk)
    assert result["grounded"] is False and result["model_grounded"] is True
    assert result["sources"] == [] and result["slips"] == []

async def test_missing_used_excerpts_falls_back_to_every_reranked_chunk(...):
    # model: grounded True, no used_excerpts key
    assert len(result["sources"]) == 3 and result["sources_fallback"] is True
    assert result["grounded"] is True

async def test_ungrounded_answer_lists_no_sources_even_if_it_names_excerpts(...):
    # model: grounded False, used_excerpts [0]
    assert result["sources"] == [] and result["grounded"] is False

def test_specific_prompt_asks_for_used_excerpts():
    assert '"used_excerpts"' in SPECIFIC_SYSTEM_PROMPT
```

Update `test_answer_specific_happy_path` and `test_answer_specific_returns_slips_apart_from_the_answer` to include `used_excerpts` (an answer without it now takes the fallback, which they shouldn't depend on). Extend `test_answer_broad_path_uses_segment_summaries` to assert `result["context"] == result["sources"]` and `result["model_grounded"] is True`.

- [ ] **Step 2: Run to verify they fail** — `docker compose exec api pytest tests/test_chat_generation.py -v`; the new tests FAIL (KeyError / extra sources).

- [ ] **Step 3: Implement.** Prompt: add the key to the JSON description ("the numbers of the excerpts your answer relies on; empty when grounded is false"); wording is the builder's. Code: a `_used_sources(result, top_chunks) -> tuple[list[TranscriptChunk], bool]` helper (chunks, fallback) keeps `_answer_specific` short.

- [ ] **Step 4: Run** — `docker compose exec api pytest`; all PASS. `ruff check` / `ruff format` clean.

- [ ] **Step 5: Show the user, wait for approval, commit** — `feat: list only the excerpts a chat answer used` (`Refs #47`)

---

### Task 2: Chat eval judges the context and measures flips and span

**Files:**
- Modify: `api/app/eval/chat.py`
- Test: `api/tests/test_eval.py`

**Interfaces:**
- Consumes: Task 1's `context`, `model_grounded`, `sources_fallback`; `first_hit_rank(retrieved: list[Span], span: Span) -> int | None` from `app/eval/retrieval.py`.
- `_judge` builds its prompt from `answer["context"]` instead of `answer["sources"]`.
- Records add `model_grounded`, `n_sources`, `sources_fallback`, and for specific questions with a span: `span_in_context: bool`, `span_in_sources: bool` (`first_hit_rank(...) is not None` over the context's / the sources' `(start_time, end_time)`).
- `summarize` adds per kind `flipped` (records with `model_grounded and not grounded`), `fallbacks` (count), `mean_sources`; for `specific` and `broad`, `false_alarms` (flipped and judged `supported`); for `specific`, `span_kept` = `span_in_sources` count / `span_in_context` count over records with `span_in_context` (None when there are none).
- `_print_table` shows `flipped`, `false_alarms`, `span_kept`, `mean_sources`.

- [ ] **Step 1: Write the failing tests**

```python
def test_chat_summary_counts_flips_false_alarms_and_span_kept():
    # specific: (a) flipped + judged supported, span in context not sources
    #           (b) not flipped, span in context and sources, 2 sources
    #           (c) out-of-scope flipped, judged declines
    s = summarize_chat(records)
    assert s["specific"]["flipped"] == 1 and s["specific"]["false_alarms"] == 1
    assert s["specific"]["span_kept"] == 0.5
    assert s["out_of_scope"]["flipped"] == 1 and "false_alarms" not in s["out_of_scope"]
```

Add `model_grounded`, `n_sources`, `sources_fallback` to the `record()` helper in `test_chat_summary_rates_checks_grounding_and_routing`.

- [ ] **Step 2: Run to verify it fails** — `docker compose exec api pytest tests/test_eval.py -v`

- [ ] **Step 3: Implement.** Update the module docstring: the judge sees what the answer model saw (the reranked chunks or the segment summaries), not the narrower used sources.

- [ ] **Step 4: Run** — full suite PASS, ruff clean.

- [ ] **Step 5: Show the user, wait for approval, commit** — `feat: judge chat answers on their context and count flipped sources` (`Refs #47`)

---

### Task 3: Measure, then document

**Files:**
- Create: `api/eval/results/chat-<date>-used-sources-run1.json`, `-run2.json`
- Modify: `docs/ARCHITECTURE.md` (chat answer flow ~line 122; chat eval ~line 234), `docs/API.md` (`sources` for specific answers), `README.md` (evaluation section)

- [ ] **Step 1: Tell the user the cost (~$0.50 for two runs) and wait for a yes.**
- [ ] **Step 2: Run twice** — `docker compose restart api`, then `docker compose exec api python -m app.eval.chat --label used-sources-run1` and `-run2`.
- [ ] **Step 3: Compare against the pass criteria** (spec §4) using the 2026-10-22 `48-question-first` runs as the baseline: `supported`, `answers_question`, `declines` within the baseline spread; `false_alarms` ≤ 2 of 40 per run; `span_kept` ≥ 0.90; report `mean_sources` and `fallbacks`. Above any limit: stop and report to the user; do not change the prompt to pass.
- [ ] **Step 4: Docs** — ARCHITECTURE: specific answers list the excerpts the model says it used, in rerank order; the grounded rule and the fallback; one short paragraph on why not inline markers, linking the spec and the citation labels file; chat eval judges against `context`. API: `sources` for a specific answer is the used excerpts. README: the results table and the marker-calibration finding.
- [ ] **Step 5: Show the user the numbers and docs, wait for approval, commit** — `docs: chat used-sources results for #47` (`Refs #47`)
- [ ] **Step 6:** `code-reviewer` agent on the branch diff; only READY clears. PR (`Closes #47`) only when the user asks.
