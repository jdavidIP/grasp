# Flashcards tab — design

Sub-project 4 of 5 for [#24](https://github.com/jdavidIP/grasp/issues/24). Issue-wide decisions are in `2026-10-03-ui-foundation-library-design.md`; the workspace shell is `2026-10-03-workspace-shell-design.md`; the chat tab (sub-project 3) is `2026-10-03-chat-tab-design.md`. Visual reference: handoff §5 (`docs/design/README.md`).

## Scope

- The Flashcards tab becomes one panel with four views — **list → config → generating → review** — replacing `FlashcardConfigModal`'s `<dialog>` (its form logic carries over).
- Restyle the deck list and review to the handoff.
- Show each card's speaker-slip `note` (#18), which the API already returns but the UI never showed; fix the `Flashcard` type, which lacks it.
- Frontend only. No backend or API changes.

Not in scope (handoff "Gaps" and `CLAUDE.md`): per-card grading ("got it / needs work"), spaced repetition, real generation progress from the server.

## 1. Structure

- **`FlashcardsPanel`** (new) owns the tab: `view: 'list' | 'config' | 'generating' | 'review'`, the reviewed deck id, and the config draft (count, scope, segment ids, difficulty, style, title). `VideoDetailPage` renders `<FlashcardsPanel videoId segments onSeek={seek} />` and drops its `reviewingDeckId` state. Workspace tab panels stay mounted, so the draft survives switching tabs.
- **Flow:**
  - list: **New deck** → config; **Review** → review of that deck.
  - config: **Cancel** → list; submit → generating.
  - generating: success → review of the new deck; failure (including `422`, every card failed grounding) → config with the draft kept and the error shown inline.
  - review: **Close** → list.
  - Deleting the deck under review → list (it can only be deleted from the list, so this covers a stale id).
- **Data:** the existing hooks in `useFlashcards.ts`, unchanged. `Flashcard` gains `note: string | null`, mirroring `FlashcardOut`.
- Styles: one `Flashcards.css`, `.fc-*` classes, Industry tokens only.

## 2. Views

### Deck list

- Header row: `<h3>Flashcard decks</h3>` and a **New deck** `.btn .btn-primary`.
- One `.blueprint` card per deck (four corner marks), `padding: var(--space-4)`, `gap: var(--space-2)`:
  - title, Barlow Condensed 600 18px; right: `.text-muted` 12px tabular "{card_count} cards · {formatRelative(created_at)}" (singular "1 card");
  - a `.text-muted` 12.5px config summary (below);
  - **Review** `.btn .btn-secondary`, **Delete** `.btn .btn-ghost` 12.5px with `window.confirm('Delete the deck "{title}"? This cannot be undone.')`.
- States: "Loading…" (muted); a fetch error with `role="alert"`; empty: "No flashcard decks yet." (muted). A delete error shows on its own deck with `role="alert"`.
- **Config summary** — `deckConfigSummary(config)` in `web/src/lib/format.ts` (component files export only components), from the stored `config` jsonb: `"Whole video · {difficulty} · {style}"` or `"{n} topics · {difficulty} · {style}"` ("1 topic"). A missing or non-string key is left out, so an older or partial config never prints "undefined".

### Config

- `<h3>New deck</h3>`, then fields with `<h6>` labels, `gap: var(--space-6)`, mapping 1:1 to the `POST /videos/{id}/flashcard-decks` payload:

| Field | Control | Values |
|---|---|---|
| `count` | `<input type="range">` 5–50 step 1, `accent-color: var(--color-accent)`, `aria-label="Number of cards"`, live value beside it in Barlow Condensed 600 20px tabular | default 12 |
| `scope` | `.seg` of native radios: "Whole video" / "Selected topics" | `whole_video`, `topics` |
| `segment_ids` | only when scope is `topics`: header "{n} of {total} selected"; one row per segment with a visually hidden native checkbox and a ■/□ marker; checked rows `border: 1px solid var(--color-accent)`, `background: var(--color-accent-100)`, else `--color-divider` border, transparent | the video's segments |
| `difficulty` | `.seg` | `easy`, `medium`, `hard`, `mixed` (default) |
| `style` | `.seg` | `definition`, `concept`, `detail`, `mixed` (default) |
| `title` | `.field` + `.input`, label "Title (generated if blank)" | optional |

- `.seg` markup per the handoff's native-radio note: `<label className="seg-opt"><input type="radio" …/>{label}</label>`.
- **Generate {count} cards** `.btn .btn-primary`; disabled with the label **"Select at least one topic"** when scope is `topics` and none is picked. **Cancel** `.btn .btn-secondary`.
- Payload: `segment_ids` only when scope is `topics`; `title` only when non-blank (trimmed).
- A generation error shows above the buttons with `role="alert"`.
- With no segments and scope `topics`: "No topics available." (muted) and the button stays disabled.

### Generating

- `<h4>Generating deck…</h4>`, a `.text-muted` line "Retrieving passages, drafting cards and checking each one against the transcript.", and "{s}s elapsed" counting every second (13px tabular, muted). The heading and status line sit in an `aria-live="polite"` region; the counter does not (it would announce every second).
- **Why not the handoff's timed checklist:** generation is one synchronous request with no progress reported; ticking steps on a timer would claim progress the app can't see. Real progress (streaming stages from the server) is a backend change, not part of this restyle.

### Review

- Header: deck title `<h3>` and **Close** `.btn .btn-ghost`.
- `<h6>Card {i} of {n}</h6>` left; the card's `difficulty` as `.tag .tag-neutral` uppercase right (omitted when null).
- **Progress strip:** one 4px-tall cell per card, `gap: 3px`, each `border: 1px solid var(--color-divider)`; past `--color-accent-300`, current `--color-accent`, upcoming transparent. `aria-hidden` (the "Card i of n" text carries it).
- **The card:** `.blueprint` with corner marks, `padding: var(--space-8) var(--space-6)`, `min-height: 250px`, 3% hover tint, `cursor: pointer`; a click anywhere on it toggles the answer.
  - `.fc-kicker` (10px, `letter-spacing: 0.1em`, uppercase, `--color-accent`): the source segment's label, looked up in the video's `segments` by `segment_id`; omitted when null or not found.
  - Front: Barlow Condensed 600 26px, `line-height: 1.16`, `overflow-wrap: anywhere`.
  - **Revealed**, in a hairline-topped block: the back (15px, `line-height: 1.6`); the card's `note` when present (`.text-muted` 13px); **Jump to {mm:ss}** `.btn .btn-ghost` when `source_start_time` isn't null, whose click calls `onSeek` and does not toggle the card.
  - **Hidden:** `.text-muted` 11px uppercase "Click to reveal answer" pinned to the bottom.
  - The card is a `<div>` (a button can't contain the Jump button); a real `<button aria-expanded>` "Show answer" / "Hide answer" inside it gives keyboard and screen-reader access.
- **← Previous** / **Next →** `.btn .btn-secondary`, each `flex: 1`, disabled at the ends. Moving hides the answer.
- **Keyboard:** the review section has `tabIndex={-1}` and is focused when review opens. Its `onKeyDown`: Space/Enter toggle the answer, ArrowLeft/ArrowRight move — Space/Enter are ignored when the event's target is a button, link or input, so they keep their native meaning there; the arrows always move (focus often sits on Next after a click). Scoped to the section, so it never fires from another tab (all tab panels stay mounted).
- A deck with no cards: "This deck has no cards." and Close. Loading: "Loading…".
- `FlashcardReview` keeps `key={deckId}` from its parent so switching decks resets the position.

## Files

| File | Change |
|---|---|
| `web/src/types/flashcard.ts` | `Flashcard.note: string \| null` |
| `web/src/lib/format.ts` | `deckConfigSummary(config)` |
| `web/src/components/FlashcardsPanel.tsx` (new) | view state, draft, flow |
| `web/src/components/FlashcardDeckList.tsx` | restyle, summary |
| `web/src/components/FlashcardConfigForm.tsx` (new) | replaces `FlashcardConfigModal.tsx` (deleted) |
| `web/src/components/FlashcardGenerating.tsx` (new) | status + elapsed counter |
| `web/src/components/FlashcardReview.tsx` | restyle, strip, kicker, note, keyboard |
| `web/src/components/Flashcards.css` (new) | `.fc-*` |
| `web/src/pages/VideoDetailPage.tsx` | Flashcards tab renders `FlashcardsPanel` |

## Testing

Vitest + RTL:
- `deckConfigSummary`: whole video; topics with plural and "1 topic"; missing keys print nothing undefined.
- Deck list: a row shows count, relative date and summary; cancelled Delete sends no request; empty state.
- Config: the slider updates "Generate {n} cards"; topics with none picked disables the button with "Select at least one topic"; the payload carries `segment_ids` only for topics and drops a blank title.
- Panel flow (fetch stubbed): New deck → config → submit shows "Generating deck…" → success opens review of the new deck; a `422` returns to config with the error shown and the draft (e.g. the title) kept; Cancel and Close return to the list.
- Review: the strip marks past/current/upcoming; Space reveals the back and the note; ArrowRight moves on and hides the answer; activating Jump seeks without toggling; Previous disabled on the first card, Next on the last; a card with no `source_start_time` and no `segment_id` shows no Jump and no kicker.
- `VideoDetailPage`: the Flashcards tab renders the panel.

Plus `typecheck`, `lint`, `build`, `npm test`.

**Manual browser check** (light and dark, desktop and narrow): generate a real 5-card deck (cents of gpt-4o-mini), review it with mouse and keyboard, a card with a note if one appears, cancel a config, delete a deck, a typed config draft survives switching tabs, and shortcuts don't fire while typing in the chat.
