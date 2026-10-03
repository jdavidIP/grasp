# Chat tab — design

Sub-project 3 of 5 for [#24](https://github.com/jdavidIP/grasp/issues/24). Issue-wide decisions are in `2026-10-03-ui-foundation-library-design.md`; the workspace shell this fills is `2026-10-03-workspace-shell-design.md`.

## Scope

- Restyle `ChatPanel` to the handoff's chat tab (handoff §4), minus suggestion chips (dropped for #24).
- **Sources survive a reload:** `GET /videos/{id}/chat` returns each assistant message's `sources` and `grounded`, for both specific and broad answers. Today they exist only for answers received in the current session, matched back by exact answer text.
- Reprocessing a video deletes its chat history, and the Reprocess button warns first.

Not in scope: inline `[n]` citation markers and showing only the sources an answer actually used. Both need a prompt change and their own eval, tracked in [#47](https://github.com/jdavidIP/grasp/issues/47). Until then, a specific answer lists every reranked chunk and a broad answer lists every segment, as the API already returns.

## 1. Persistence

**Why not snapshot the sources?** A reprocess deletes the video's segments, and its chunks cascade with them; both come back with new ids. Saved `cited_chunk_ids` would then point at nothing (the array has no foreign key). Two fixes were considered:

- **Snapshot** each answer's sources (label, times, text) as jsonb on the message. Survives a reprocess, but duplicates chunk text on every message.
- **Clear the chat on reprocess** (chosen). Reprocessing is only ever user-triggered (the Reprocess button → `POST /videos/{id}/reprocess`). It already rebuilds the topics, so dropping the chat that cites the old ones is reasonable once the user is warned. Ids then can't outlive their chunks, and nothing is duplicated.

Tradeoff recorded in `docs/DATA_MODEL.md`.

**Schema** (one Alembic migration):
- `DELETE FROM chat_messages` — a deliberate one-off clear, so no row lacks the new columns. (Single local user; user approved.)
- Add `scope text NULL` with a check constraint `scope IN ('broad', 'specific')`.
- Add `grounded boolean NULL`.
- Both are set on assistant rows and stay null on user rows. `cited_chunk_ids` is unchanged.
- Downgrade drops the two columns (the cleared rows aren't restored).

**Why broad answers need no ids:** a broad answer always cites *all* of the video's segments. Because the chat is cleared whenever segments are rebuilt, the video's current segments are exactly the ones the answer saw, so `scope = 'broad'` is enough to rebuild them.

## 2. API

**`POST /videos/{id}/chat`:** the assistant row also saves `scope` (from the `path` that `answer_question` already returns) and `grounded`. The response doesn't change.

**`GET /videos/{id}/chat`:** `ChatMessageOut` gains:
- `sources: list[ChatSource]` — empty for user rows;
- `grounded: bool | None` — null for user rows.

The router stays thin: it calls a new service function in `app/generation/chat.py` (e.g. `load_history(session, video_id)`) that returns the messages with sources rebuilt, in two queries for the whole history:
- **Chunks:** every id in any message's `cited_chunk_ids`, joined to its segment for the label. Each message's sources come back in its saved id order. An id with no matching chunk is skipped.
- **Segments:** the video's segments in `order_index` order, loaded once and used for every broad row (`chunk_id: null`, segment span, summary as `text` — the same shape `_answer_broad` returns).
- Specific rows with no `cited_chunk_ids` (e.g. retrieval found nothing) get `sources: []`.

**Reprocess:** `run_reprocessing` (`app/ingestion/videos.py`) deletes the video's `chat_messages` in the same transaction as `delete(TranscriptSegment)`, after analysis succeeds. A failed reprocess keeps the chat, as it keeps the segments. The full-ingestion path (no saved transcript) has no segments to cite, so it's left alone.

**Docs:** `docs/API.md` — history now carries `sources`/`grounded`, and reprocess clears chat. `docs/DATA_MODEL.md` — the new columns and the clear-on-reprocess tradeoff above.

## 3. Frontend

**Types:** `ChatMessage` in `web/src/types/chat.ts` gains `sources: ChatSource[]` and `grounded: boolean | null`, mirroring the schema.

**`ChatPanel`:** rewritten to render straight from history. The session map that matched answers by text is deleted. Styles go in a new `ChatPanel.css` with `.chat-*` classes and Industry tokens only.

**Layout:** the panel is a flex column filling the tab panel: a scrolling thread above, the composer pinned below. `.workspace-panel:not([hidden]):has(> .chat-panel)` drops the outer padding and scrolling for the chat tab only (CSS in `ChatPanel.css`), so `WorkspaceTabs` and the other tabs don't change. The thread keeps `padding: var(--space-6)`.

**Thread** (`display: flex; flex-direction: column; gap: var(--space-8)`):
- **User message:** a row — a 40px-wide `.text-muted` 11px uppercase "You" label, then the question in Barlow Condensed 600, 20px, `line-height: 1.22`.
- **Assistant message:** `padding-left: calc(40px + var(--space-3))`, column with `gap: var(--space-4)`.
  - Answer: 15px, `line-height: 1.62`, `text-wrap: pretty`.
  - `grounded === false`: a `.tag .tag-outline` reading "Not covered in this video", and no sources list. Not styled as an error.
  - Otherwise, when a **specific** answer has sources:
    - The list is a native `<details>`, **closed by default** so the answer reads first. Its `<summary>` reads "Sources ({n})", styled like the design's muted `<h6>` over a hairline.
    - One row per source: index `1.` (11px tabular, `--color-accent-700`), then a `<button type="button">` reading `{segment_label} @ {mm:ss}` (13px tabular, `--color-accent-700`; hover `--color-accent` + underline) that calls `onSeek(start_time)`, and under it a native `<details>` with a muted 11px uppercase `<summary>` "Read transcript" holding the chunk's full text (12.5px, `line-height: 1.5`, 72% text color). Closed by default; each row opens on its own.
  - A **broad** answer shows no sources list: its sources are always every segment, which the topics list beside it already shows. The API still returns them.
  - *Revised after the browser check:* the first version quoted each source's full text inline (handoff §4), and broad answers listed every segment. Specific chunks are ~250 tokens, so five sources ran to ~60 lines and buried the answer.
- **Empty state:** "Ask anything about this video." (muted).
- **Loading / error:** "Loading…" muted; a history error with `role="alert"`.

**Pending:** while sending, the question shows immediately as a user message (from `sendMessage.variables`), followed at the assistant indent by a `.text-muted` 12px uppercase "Retrieving…" line in an `aria-live="polite"` region. On failure the question stays in the input for a retry and the error shows with `role="alert"`.

**Scrolling:** an end marker below the thread is `scrollIntoView`'d when the message count changes or a send starts.

**Composer:** `border-top: 1px solid var(--color-divider)`, `padding: var(--space-3)`, a row:
- `.input` (`flex: 1`) with `aria-label="Ask about this video"`; Enter submits (native form submit).
- **Send** `.btn .btn-primary`, `padding-inline: var(--space-6)`, disabled while pending or when the trimmed input is empty.
- **Clear** `.btn .btn-ghost`, 12.5px. Confirms with `window.confirm` ("Clear the chat history for this video? This cannot be undone.") before `DELETE /videos/{id}/chat`; disabled while clearing or when there's no history. A clear error shows with `role="alert"`.

**Reprocess warning:** `VideoDetailPage`'s Reprocess click asks `window.confirm("Reprocessing rebuilds this video's topics and deletes its chat history. Continue?")` and only fires when confirmed.

## Files

| File | Change |
|---|---|
| `api/alembic/versions/<new>_chat_scope_grounded.py` | Clear `chat_messages`; add `scope` (+ check) and `grounded`. |
| `api/app/models/chat_message.py` | `scope`, `grounded` columns. |
| `api/app/schemas/chat.py` | `ChatMessageOut` gains `sources`, `grounded`. |
| `api/app/generation/chat.py` | `load_history` rebuilds sources. |
| `api/app/routers/chat.py` | POST saves `scope`/`grounded`; GET calls `load_history`. |
| `api/app/ingestion/videos.py` | Reprocess deletes the video's chat. |
| `docs/API.md`, `docs/DATA_MODEL.md` | As in §2. |
| `web/src/types/chat.ts` | `sources`, `grounded` on `ChatMessage`. |
| `web/src/components/ChatPanel.tsx` + `.css` | Rewrite per §3. |
| `web/src/pages/VideoDetailPage.tsx` | Reprocess confirm. |

## Testing

**pytest** (only on rows the tests create — tests share the dev database):
- History for a specific answer returns its chunk sources in saved order, with segment labels.
- History for a broad answer returns every segment of the video, `chunk_id: null`.
- An ungrounded answer comes back with `grounded: false`; user rows have `sources: []` and `grounded: null`.
- A successful reprocess deletes the video's chat; a reprocess whose analysis fails keeps it.

LLM calls are stubbed, as in the existing chat tests. Plus `alembic check` after the model change, and `ruff`.

**Vitest + RTL:**
- A specific answer's sources render; clicking a row calls `onSeek` with its `start_time`.
- A broad answer lists no sources.
- The sources list and each source's transcript sit in closed `<details>` until opened.
- `grounded: false` shows the tag and no sources list.
- While sending, the question and "Retrieving…" appear.
- Clear with the confirm cancelled sends no request.
- Reprocess with the confirm cancelled sends no request.
- The existing `ChatPanel.test.tsx` updates to the new data shape.

Plus `typecheck`, `lint`, `build` and `npm test`.

**Manual browser check** (light and dark, desktop and narrow): ask a specific and a broad question, reload, and confirm both keep their sources and seek; an out-of-scope question shows the tag; the composer stays pinned while the thread scrolls; a typed question survives switching tabs; Reprocess warns and, once done, the chat is empty.

## Addendum: speaker slips section and topic list clamp

Added on the same branch after the first review gate (user request).

### Speaker slips as their own section

**Today:** when an answer relies on a known speaker slip (#34), `_with_slip_notes` appends a sentence to the answer text — *(The video says "values from 0 to 3" here; the speaker means "values from 0 to 2".)* — and that sentence is saved as part of the message content.

**Change:** the slips travel as a separate attribute instead.
- `answer_question` returns `slips: list[{said, meant}]` — the known slips the model says its answer relies on (`slips_used`), deduplicated, in the order given; empty for a decline (`grounded: false`), as today. The answer text is the model's answer alone.
- `ChatResponse` and `ChatMessageOut` gain `slips: list[ChatSlip]` (`ChatSlip = {said: str, meant: str}`); empty for user rows and for answers that used none.
- `chat_messages` gains `slips jsonb NULL` (assistant rows; null when none), so slips survive a reload. No backfill: existing rows were cleared by this branch's first migration, and any chat since has notes in its text.
- The model's own chat history (`HISTORY_LIMIT` turns) now carries answers without notes.
- **Why `{said, meant}` and not finished sentences:** the UI owns the wording, and a later timestamp (seek to where it was said) needs `said` to find the chunk.
- **Not in scope:** timestamps / seeking for slips.

**Chat eval:** the judge marks "the corrected fact with no mention of the discrepancy" as an unsupported silent correction; the appended note was that mention. The eval must judge what the user sees, so `app/eval/chat.py` judges the answer plus its notes, formatted exactly as today's note (`with_slip_notes(answer, slips)` in `app/generation/chat.py`, used only by the eval). The judge's input is then byte-identical to today's, so no paid eval run is needed; a unit test pins the format.

**UI:** under the answer (before Sources), when `grounded !== false` and `slips.length > 0`: a closed `<details>` styled like the sources list, summary "Speaker slips ({n})", holding one line per slip: *The video says "{said}"; the speaker means "{meant}".* Shown for broad and specific answers alike.

### Topic list clamped and scrollable

- **Side by side:** the left column is held to the chat panel's height. `.workspace-columns` becomes a size container (`container-type: inline-size`); under `@container (min-width: 973px)` the left column stretches to the row (`align-self: stretch`; a container query can't style the container itself), and the topics section takes the remaining height (`flex: 1 1 0; min-height: 160px; contain: size`), so it adds nothing to the row's height and the row takes the panel's `min(80vh, 840px)`. The topic list scrolls inside it; the "Topics / n segments" header stays put.
- **Stacked** (below the container breakpoint): the topic list gets `max-height: min(80vh, 840px)` and scrolls.
- The 160px floor keeps the list usable on short screens where the player alone nearly fills 80vh; the left column then runs past the panel.
- The 973px breakpoint is where the columns wrap: 520 + 430 + the gap, about 23px at that width. Checked pixel by pixel across the boundary in the browser; it must move with the columns' flex-basis values.
- CSS only; checked in the browser (jsdom doesn't load CSS).
