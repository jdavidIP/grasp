# Handoff: Grasp — Study Companion UI

## Overview

A visual and interaction design for **Grasp**, the existing YouTube study app in this repo (FastAPI + Postgres/pgvector API, React + Vite web client). The current web client is unstyled semantic HTML; this design gives it a complete visual layer and restructures the video page into a two-column workspace.

It covers five surfaces: **Library**, the **video workspace shell** (player + topic segments on the left, a tabbed panel on the right), **Chat with citations**, **Flashcard decks + review**, and **Quizzes: config → take → results → attempt history**.

The design was built directly against `docs/DATA_MODEL.md`, `docs/API.md`, and the existing components in `web/src/`. Field names, status enums, config payload shapes, and grading semantics in the mock match the real contracts — they are not invented. Two deliberate exceptions are called out under **Gaps against the current codebase**.

## About the Design Files

The files in `design/` are a **design reference created in HTML** — a prototype showing intended look and behavior. They are **not production code to copy**.

`design/Grasp - Study Companion.dc.html` is a single self-contained prototype: markup in an `<x-dc>` template, state in a `class Component` at the bottom of the file, all styling inline or via `design/industry.css`. `design/support.js` is only the runtime that makes that prototype file open in a browser — **do not port it**.

The task is to **recreate this design in the existing `web/` client**: React 19 + TypeScript + Vite, `react-router`, and TanStack Query, with the hooks and API modules already in `web/src/hooks/` and `web/src/api/`. All data fetching, mutation, and routing already exist — this is a presentation-layer job plus some restructuring of `VideoDetailPage`.

Open `design/Grasp - Study Companion.dc.html` in a browser to interact with it. Everything is clickable: add a video, open the first library row, ask a chat question, generate a deck, take a quiz.

## Fidelity

**High-fidelity.** Colors, typography, spacing, borders, and states are final and come from a design system (see **Design Tokens**). Recreate pixel-for-pixel. The prototype's *fake data* (the transformers lecture, the seeded chat answers, the hardcoded attempt list) is placeholder — real data comes from the API.

---

## Design system: Industry

The whole design sits on a design system called **Industry**, shipped here as `design/industry.css`. **Copy this file into the web client** (suggested: `web/src/styles/industry.css`, imported once from `web/src/main.tsx` alongside or in place of `index.css`).

Its character, so you preserve it when you build new pieces:

- **A technical wireframe.** Light steel-grey ground, one steel-blue accent, no second color.
- **Square corners everywhere.** `.card`, `.btn`, `.input`, `.tag`, `.seg` are all forced to `border-radius: 0`.
- **Cards and figures are line drawings, not filled surfaces** — transparent background, 1px hairline border. The solid accent primary button is the single deliberate exception.
- **Blueprint registration marks.** Framed objects get `class="blueprint"` plus exactly four children: `<i class="corner tl">`, `tr`, `bl`, `br`. These draw `+` crosshairs outside the box corners. Never drop them from a framed element.
- **Barlow Condensed** for headings, **Barlow** for body. Both are `@import`ed at the top of `industry.css`.

Use the system's classes (`.btn`, `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-icon`, `.tag`, `.tag-accent`, `.tag-neutral`, `.tag-outline`, `.input`, `.field`, `.seg`, `.seg-opt`, `.card`, `.table`, `.nav`, `.nav-brand`, `.text-muted`, `.blueprint`, `.elev-md`) rather than writing parallel ones. Take every color, size, and spacing value from its `var(--*)` tokens — do not hard-code a hex or a px value the tokens already carry.

### A note on the segmented control

`industry.css` styles `.seg` / `.seg-opt` for **native radio inputs** (`.seg-opt:has(input:checked)`). The prototype fakes that with inline background/color because of a constraint in the prototyping environment. **In the real build, use the native markup** — it's cleaner and gets focus handling for free:

```tsx
<div className="seg">
  {options.map((o) => (
    <label className="seg-opt" key={o.value}>
      <input type="radio" name={name} value={o.value}
             checked={value === o.value}
             onChange={() => onChange(o.value)} />
      {o.label}
    </label>
  ))}
</div>
```

Same for the checkbox-style multi-selects (segment picker, question types, quiz options) — the prototype draws `■`/`□` and `●`/`○` glyphs as stand-ins. Use real `<input type="checkbox">` / `<input type="radio">` with `.radio` + `.dot`, or keep the glyph treatment if you prefer the look, but keep the inputs in the DOM and visually hidden so keyboard and screen-reader behavior survive.

---

## Screens / Views

### 1. App header (all routes)

Sticky, `z-index: 30`, `background: var(--color-bg)`, `border-bottom: 1px solid var(--color-divider)`. Inner wrapper `.nav`, `max-width: 1460px`, centered, `padding: var(--space-3) clamp(14px, 3vw, 28px)`.

| Element | Spec |
|---|---|
| Brand `GRASP` | `.nav-brand` (Barlow Condensed 600, 18px), `letter-spacing: 0.02em`, `margin-right: auto` from the class. Links to `/`. |
| Meta text | `.text-muted`, 11px, `letter-spacing: 0.08em`, uppercase, tabular numerals. Library: `"{n} videos"`. Video page: the `youtube_id`. |
| Theme toggle | `.btn .btn-icon` (36×36), Lucide `sun` / `moon` at 17px, `stroke-width="1.5"`. |

### 2. Library (`/`)

`max-width: 1020px`, centered, `padding: clamp(24px,4vw,44px) clamp(14px,3vw,28px) 80px`.

- **`<h1>Library</h1>`** — 42px Barlow Condensed 600, `letter-spacing: -0.015em`.
- **Intro paragraph** — `.text-muted`, 15px, `max-width: 58ch`, `text-wrap: pretty`.
- **Add-video row** — `display: flex; gap: var(--space-2); flex-wrap: wrap`, margin `var(--space-6) 0 var(--space-2)`. An `.input` (`flex: 1 1 320px; min-width: 0`) with placeholder `https://www.youtube.com/watch?v=…`, and a `.btn .btn-primary .blueprint` (with the four corner marks) reading **Add video**, `padding-inline: var(--space-6)`. Enter in the field submits.
- **Error line** — below the row when `POST /videos` fails, 13px, `color: var(--color-accent-800)`, `role="alert"`. Show the API's `detail` string. `409` → "already in your library".
- **List header** — a flex row, `border-bottom: 1px solid var(--color-divider)`, `padding-bottom: var(--space-2)`. Left: `<h6>` with the count. Right: `<h6 class="text-muted">Newest first</h6>`. (`h6` is 13px, `letter-spacing: 0.08em`, uppercase by default in the system.)
- **Video rows** — `display: flex; gap: var(--space-4); flex-wrap: wrap; align-items: center`, `padding: var(--space-4) var(--space-2)`, `border-bottom: 1px solid color-mix(in srgb, var(--color-text) 8%, transparent)`. Hover: `background: color-mix(in srgb, var(--color-text) 4%, transparent)`.

  | Part | Spec |
  |---|---|
  | Thumbnail | 124×70, `border: 1px solid var(--color-divider)`. Render `thumbnail_url` with `object-fit: cover`; the prototype's diagonal hatch is the empty fallback. Duration badge bottom-right: 11px tabular, `background: var(--color-bg)`, `padding: 0 4px`, hairline border. |
  | Title | Barlow Condensed 600, 19px, `line-height: 1.18`, `text-wrap: pretty`. |
  | Sub-line | `.text-muted` 13px — `"{channel} · added {relative time}"`. |
  | Note line | 12.5px, `line-height: 1.45`. On `failed`: `color: var(--color-accent-800)` and `role="alert"`, showing `error_message` verbatim. On `pending`/`processing`: muted, showing the current stage. |
  | Status tag | `.tag`, uppercase, `letter-spacing: 0.08em`. `ready` → `.tag-accent`; `failed` → `.tag-outline`; `pending`/`processing` → `.tag-neutral`. **Print the raw enum value** (`ready`, `processing`, `pending`, `failed`) — it matches `videos.status` and the current UI. |
  | Delete | `.btn .btn-ghost`, Barlow 12.5px. Confirm before firing `DELETE /videos/{id}` — it cascades to segments, chunks, chat, decks, quizzes, and attempts. |

  Thumbnail and text block are the click target → `/videos/{id}`. Delete must not bubble to it.

- **Empty state** — keep the existing copy: "No videos yet. Add one above to get started."
- **Polling** — after `POST /videos` returns `201` with `status: "pending"`, poll `GET /videos/{id}` until `ready` or `failed`, and reflect the status tag and note line live.

### 3. Video workspace (`/videos/:id`)

`max-width: 1460px`, `padding: clamp(16px,2.5vw,26px) clamp(14px,3vw,28px) 56px`. A **← Library** `.btn .btn-secondary` sits above, `margin-bottom: var(--space-4)`.

Two columns: `display: flex; flex-wrap: wrap; gap: clamp(20px,2.2vw,30px); align-items: flex-start`.

- Left: `flex: 1 1 520px; min-width: 0`, column, `gap: var(--space-6)`.
- Right: `flex: 1 1 430px; min-width: 0`, `height: min(80vh, 840px)`, `class="blueprint"` with the four corner marks, `background: var(--color-bg)`.

Because both have `flex-wrap` and `min-width: 0`, they stack naturally on narrow viewports. Desktop-first; it just needs to not break.

**Left column, top to bottom:**

1. **Title row** — `<h2>` (32px Barlow Condensed) with the video title, and below it `.text-muted` 13px tabular: `"{channel} · {duration} · {n} segments"`. Right-aligned in the same row: the status `.tag` and a **Reprocess** `.btn .btn-secondary` firing `POST /videos/{id}/reprocess`. Per the existing page, Reprocess is hidden while status is `pending` or `processing`.
2. **Player** — `<figure class="blueprint">` with corner marks, `aspect-ratio: 16/9`. Mount the existing `YouTubePlayer` here. Only rendered when `status === 'ready'`.
3. **Scrub row** — `margin-top: calc(var(--space-2) * -1)`, `gap: var(--space-3)`: current time (13px tabular, `color: var(--color-accent-700)`, `min-width: 46px`), a 6px-tall track (`border: 1px solid var(--color-divider)`, `background: var(--color-surface)`) with an accent fill, and total duration (`.text-muted` 13px tabular). This is a **display of player state** — read position from the YouTube iframe API. Making it seekable by dragging is optional and not designed.
4. **Topics** — header row (`<h6>Topics</h6>` / `<h6 class="text-muted">{n} segments</h6>`) over a hairline. Each `transcript_segment` is a clickable row, `padding: var(--space-3) var(--space-1)`, hairline bottom, same 4% hover:
   - Range, `flex: 0 0 auto; min-width: 92px`, 12.5px tabular, `color: var(--color-accent-700)` — `formatTime(start_time)–formatTime(end_time)`.
   - `label` in Barlow Condensed 600, 16px.
   - `summary` in `.text-muted` 13px, `line-height: 1.45`, `text-wrap: pretty`.

   Clicking seeks the player to `start_time`.

**Right column** is the tabbed panel. Tab strip: `display: flex`, `border-bottom: 1px solid var(--color-divider)`; each tab `flex: 1`, `padding: var(--space-3)`, `border-right: 1px solid var(--color-divider)`, Barlow Condensed 600 15px, `letter-spacing: 0.02em`. Active: `background: var(--color-accent); color: var(--color-bg)`. Inactive: transparent on `var(--color-text)`. Tabs: **Chat**, **Flashcards**, **Quizzes**. Below it, one scroll region: `flex: 1; min-height: 0; overflow-y: auto; padding: var(--space-6)`.

Use real `role="tablist"` / `role="tab"` / `role="tabpanel"` semantics with arrow-key navigation.

### 4. Chat tab

Messages: `display: flex; flex-direction: column; gap: var(--space-8)`.

**User message** — a row: a 40px-wide `.text-muted` 11px uppercase `You` label, then the question in **Barlow Condensed 600, 20px**, `line-height: 1.22`. The question is typographically the loudest thing in the thread; the answer is body text. Keep that inversion.

**Assistant message** — indented `padding-left: calc(40px + var(--space-3))` to align under the question, `gap: var(--space-4)`:

- **Answer body** — 15px, `line-height: 1.62`, `text-wrap: pretty`.
- **Citation markers** — superscript numbered markers `[1]`, `[2]` inline in the prose, as `<button>`s: `vertical-align: super`, 11px tabular, `color: var(--color-accent-700)`, no border/background. Hover: `color: var(--color-accent)` + underline. Click seeks the player to that source's `start_time`.
- **Sources list** — `<h6 class="text-muted">Sources</h6>` over a hairline, then one row per source: index (`1.`, 16px wide, 11px tabular, accent-700), the chunk text in quotes (12.5px, `line-height: 1.5`, `color: color-mix(in srgb, var(--color-text) 72%, transparent)`), and a meta line beneath it, 11px tabular accent-700: `"{segment_label} @ {mm:ss}"`. Whole row is clickable → seek. Hover: the 4% tint.
- **Broad answers** — when the response came from segment summaries (`sources[].chunk_id === null`), the heading reads **"Sources — segment summaries"** and each meta line shows the full span: `"{segment_label} @ {mm:ss}–{mm:ss}"`.
- **Ungrounded answers** — when `grounded === false`, render no sources list and show a `.tag .tag-outline` reading **"Not covered in this video"**. This is a feature, not an error state — do not style it as a failure.
- **Pending** — while the mutation is in flight, a `.text-muted` 12px uppercase **"Retrieving…"** line at the same indent.

**Composer** — pinned below the scroll region, `border-top: 1px solid var(--color-divider)`, `padding: var(--space-3)`:

- **Suggestion chips** (only while the thread is short) — `.btn .btn-secondary` overridden to Barlow 400 13px, `padding: 4px 10px`. Clicking sends immediately.
- A row with an `.input` (`flex: 1`), a **Send** `.btn .btn-primary` (`padding-inline: var(--space-6)`, disabled while pending), and a **Clear** `.btn .btn-ghost` 12.5px firing `DELETE /videos/{id}/chat`.

Enter submits. Clear should confirm first.

> **Known API gap, already commented in `ChatPanel.tsx`:** `GET /videos/{id}/chat` returns messages without sources, so citations only exist for answers received this session. The current code matches them back by exact answer text. This design leans heavily on citations, so **the better fix is server-side**: `chat_messages.cited_chunk_ids` is already in the schema — have the history endpoint hydrate and return the sources. If that's out of scope, keep the existing session-map workaround and accept that reloaded history has no markers.

### 5. Flashcards tab

Four views in one panel: `list` → `config` → `generating` → `review`.

**Deck list** — an `<h3>Flashcard decks</h3>` / **New deck** `.btn .btn-primary` header row, then one `.blueprint` card per deck (`padding: var(--space-4)`, `gap: var(--space-2)`, **with** corner marks):

- Title: Barlow Condensed 600, 18px. Right: `.text-muted` 12px tabular `"{card_count} cards · {relative created_at}"`.
- A `.text-muted` 12.5px line summarising the stored `config` jsonb — e.g. `"3 segments · mixed · concept"` or `"whole_video · medium · mixed"`. This is exactly why `config` is stored as jsonb; surface it.
- **Review** (`.btn .btn-secondary`) and **Delete** (`.btn .btn-ghost` 12.5px).

**Config form** — `gap: var(--space-6)`, each field labelled with an `<h6>`. Fields map 1:1 to the `POST /videos/{id}/flashcard-decks` payload:

| Field | Control | Values |
|---|---|---|
| `count` | Range slider, `accent-color: var(--color-accent)`, with the live value at Barlow Condensed 600 20px tabular beside it | 5–50, default 12 |
| `scope` | `.seg` — "Whole video" / "Selected topics" | `whole_video`, `topics` |
| `segment_ids` | Checkbox list, only when scope is `topics` | The video's segments; header shows `"{n} of {total} selected"` |
| `difficulty` | `.seg` | `easy`, `medium`, `hard`, `mixed` |
| `style` | `.seg` | `definition`, `concept`, `detail`, `mixed` |
| `title` | `.field` + `.input` | Optional; label says "generated if blank" |

Segment rows: `padding: var(--space-2)`, `border: 1px solid` — `var(--color-accent)` when checked else `var(--color-divider)` — `background: var(--color-accent-100)` when checked else transparent. Selected marker in `var(--color-accent)`.

Submit is `.btn .btn-primary` reading **"Generate {count} cards"**, disabled with the label **"Select at least one segment"** when scope is `topics` and nothing is picked. A **Cancel** `.btn .btn-secondary` returns to the list.

**Generating** — `<h4>Generating deck…</h4>` and a three-step checklist: *"Retrieving chunks for the selected segments"*, *"Drafting cards"*, *"Checking every card against the transcript"*. Steps mark `▸` (current, full-strength text) → `✓` (done, accent). Since generation is synchronous, drive this on a timer and settle when the request resolves. Handle `422` ("every card failed grounding — nothing saved") as an inline error back on the config form, not a crash.

**Review** — matches `FlashcardReview.tsx`'s behavior exactly:

- Header: deck title `<h3>` + **Close** `.btn .btn-ghost`.
- `<h6>Card {i} of {n}</h6>` on the left; the card's `difficulty` as a `.tag .tag-neutral` uppercase on the right.
- A progress strip: one 4px cell per card, `gap: 3px`, each `border: 1px solid var(--color-divider)`. Past cards `var(--color-accent-300)`, current `var(--color-accent)`, upcoming transparent.
- The card itself: `.blueprint` **with corner marks**, `padding: var(--space-8) var(--space-6)`, `min-height: 250px`, clickable to toggle reveal. Hover: 3% tint. Contents: `.card-kicker` (10px, `0.1em`, uppercase, accent) with the source segment's label; the **front** in Barlow Condensed 600, 26px, `line-height: 1.16`. When revealed, a hairline-topped block adds the **back** at 15px `line-height: 1.6` and a **"Jump to {mm:ss}"** `.btn .btn-ghost` (stop propagation so it doesn't re-flip the card). When hidden, a muted 11px uppercase **"Click to reveal answer"** pinned to the bottom.
- **← Previous** / **Next →** below, each `flex: 1`, disabled at the ends.

Keyboard: space/enter to flip, arrows to move.

### 6. Quizzes tab

Six views: `list` → `config` → `generating` → `take` → `results`, plus `history`.

**Quiz list** — like the deck list. Each `.blueprint` card shows the title, `"Best {n}%"` in `var(--color-accent-700)` (or a muted **"Never attempted"** when `best_score` is `null`), a `.text-muted` meta line `"{question_count} questions · {n} attempts"`, and **Take** / **History** / **Delete**.

**Config form** — maps to `POST /videos/{id}/quizzes`:

| Field | Control | Values |
|---|---|---|
| `count` | Range slider | 3–30, default 6 |
| `scope` | `.seg` | `whole_video`, `topics` (+ segment picker, same as flashcards) |
| `question_types` | Checkbox list with hint lines | `multiple_choice` — "Exactly one correct option"; `multi_select` — "Select all that apply — all-or-nothing grading"; `true_false` — "Always two options" |
| `options_per_question` | `.seg` — hidden when only `true_false` is selected | 3, 4, 5 — default 4 |
| `difficulty` | `.seg` | `easy`, `medium`, `hard`, `mixed` |

The API requires a non-empty `question_types`; the UI enforces it by refusing to uncheck the last one.

**Taking a quiz** — **all questions on one page in a single scrolling form with one submit.** This follows the real contract: `POST /quizzes/{id}/attempts` takes every answer at once, and a skipped question counts as incorrect. Do not paginate it.

Each question: a 2-digit ordinal (`01`) in Barlow Condensed 600 14px tabular accent-700, the prompt in Barlow Condensed 600 20px `line-height: 1.18`, and beneath it a `.text-muted` 11.5px uppercase type label — *"Multiple choice — one answer"*, *"Select all that apply"*, or *"True / false"*. Options are indented `calc(14px + var(--space-3))`, each `padding: var(--space-3)`, bordered accent when selected with an `var(--color-accent-100)` fill. `multi_select` uses checkboxes, everything else radios.

Footer above the submit: a hairline, then `.text-muted` 12.5px **"{n} of {m} answered. Unanswered questions count as incorrect."** and a full-width **Submit** `.btn .btn-primary`.

Never request or hold `is_correct` / `explanation` client-side before submit — `GET /quizzes/{id}` withholds them deliberately.

**Results** — driven entirely by the submit response:

- Score: `Math.round(score * 100) + '%'` at **Barlow Condensed 600, 52px**, `line-height: 0.9`, tabular. Beside it, muted 14px: `"{correct} of {total} correct · all-or-nothing, no partial credit"`.
- One block per question, `padding: var(--space-4)`. Correct: `border: 1px solid var(--color-accent-300)`, `background: var(--color-accent-100)`. Incorrect: `var(--color-divider)` / `var(--color-neutral-200)`.
  - `✓` or `✕` mark in `var(--color-accent-800)` / `var(--color-text)`, then the prompt in Barlow Condensed 600 17px.
  - **Every option** is listed at 13px with a mark and a right-aligned 11px uppercase note: `✓` + "correct answer", `✕` + "your answer", `✓` + "your answer · correct", or `·` and nothing. Correct options in `var(--color-accent-800)`, your wrong pick in `var(--color-text)`, the rest muted. This renders `selected_option_ids` vs `correct_option_ids` and is what makes `multi_select` legible.
  - "You skipped this question." when `selected_option_ids` is empty.
  - The `explanation` at 13px, `line-height: 1.55`, `color: color-mix(in srgb, var(--color-text) 75%, transparent)`.
  - A **"Jump to {mm:ss}"** `.btn .btn-ghost` from `source_start_time` (omit when null).
- Footer: **Retake** (`.btn .btn-primary`) and **Attempt history** (`.btn .btn-secondary`).

**Attempt history** — `GET /quizzes/{id}/attempts`, newest first, as a `.table`: **Completed** / **Correct** (right-aligned `"{correct_count} / {question_count}"`, muted) / **Score** (right-aligned percent, `var(--color-accent-700)` at ≥70%, else `var(--color-text)`). A **Take it again** `.btn .btn-primary` below. Rows should ideally open that attempt's detail via `GET /quizzes/{id}/attempts/{attempt_id}`, reusing the results renderer — the prototype doesn't show it but the endpoint and the component both exist.

---

## Interactions & Behavior

| Behavior | Spec |
|---|---|
| Navigation | `/` → `/videos/:id` on a library row click. `← Library` goes back. Brand mark goes home. |
| Tabs | Client-only state on the video page. Consider syncing to a `?tab=` param so a reload keeps the tab. |
| Seeking | Every timestamp in the panel — citation markers, source rows, topic rows, card "Jump to", results "Jump to" — sets player position. The existing `seekSeconds` state in `VideoDetailPage` already carries this; keep the pattern. |
| Toast | On seek and on non-blocking API results. Fixed, bottom-center, 28px up, `z-index: 50`, `.blueprint .elev-md`, `background`/`border-color: var(--color-accent)`, `color: var(--color-bg)`, 13px tabular, `padding: var(--space-2) var(--space-6)`, with corner marks. Auto-dismisses at **1900ms**. In the real app use it for seek confirmation and for mutation success/failure. |
| Hover | Rows: `background: color-mix(in srgb, var(--color-text) 4%, transparent)`. Flashcard: 3%. Buttons: from `industry.css` — don't re-specify. |
| Focus | `:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }` from the system. Never leave a default blue ring. |
| Disabled | `opacity: 0.45; cursor: not-allowed` from the system. |
| Transitions | None. The system is static and crisp — no fades, no slides. The only motion is the generation checklist advancing. |
| Errors | Inline, adjacent to the action that failed, `role="alert"`, in `var(--color-accent-800)`. Show the API's `detail` string. Ingestion failures aren't error responses — they land in `videos.status = 'failed'` with `error_message`. |
| Responsive | Desktop-first. Both workspace columns are `flex: 1 1 <basis>` with `min-width: 0`, so they stack under ~1000px. No fixed widths on text containers. |

## State Management

Server state is already handled by the existing TanStack Query hooks (`useVideos`, `useChat`, `useFlashcards`, `useQuizzes`) — reuse them; this design adds no new endpoints.

New **client** state:

| State | Scope | Notes |
|---|---|---|
| `activeTab` | Video page | `'chat' \| 'flashcards' \| 'quizzes'` |
| `seekSeconds` | Video page | Already exists |
| `theme` | App | `'light' \| 'dark'`, persisted to `localStorage` under `grasp-theme` |
| `flashcardView` | Flashcards tab | `'list' \| 'config' \| 'generating' \| 'review'` |
| deck config draft | Flashcards tab | count / scope / segmentIds / difficulty / style / title |
| `cardIndex`, `revealed` | Review | Reset on deck change — the existing code does this with `key={deckId}`; keep that |
| `quizView` | Quizzes tab | `'list' \| 'config' \| 'generating' \| 'take' \| 'results' \| 'history'` |
| quiz config draft | Quizzes tab | count / scope / segmentIds / questionTypes / optionsPerQuestion / difficulty |
| `selections` | Taking | `Record<questionId, optionId[]>`; remount with `key={quizId}` |
| `attemptResult` | Results | The submit response; drives the entire results view |
| `toast` | App | `string \| null`, cleared on a 1900ms timer |

## Design Tokens

All of these are already in `design/industry.css` — **read them from the CSS variables, don't retype the hexes.** Listed for reference.

**Core (light)**

| Token | Value |
|---|---|
| `--color-bg` | `#f2f2f3` |
| `--color-surface` | `#e9e9ea` |
| `--color-text` | `#1d1f20` |
| `--color-accent` | `#5980a6` |
| `--color-divider` | `color-mix(in srgb, #1d1f20 16%, transparent)` |

**Accent ramp** — `100 #eef6ff`, `200 #d6ebff`, `300 #b5d9fd`, `400 #94bce3`, `500 #749dc4`, `600 #597ea3`, `700 #416180`, `800 #2c455d`, `900 #1d2d3d`.

**Neutral ramp** — `100 #f5f5f8`, `200 #e7e7ea`, `300 #d4d4d7`, `400 #b7b7ba`, `500 #98989b`, `600 #7a7a7d`, `700 #5d5d60`, `800 #424244`, `900 #2b2b2d`.

> Accent-on-ground is tuned to ~3:1 — fine for icons, large text, and chrome, **not** for body copy. For paragraph-size accent text use `--color-accent-700`. That's why every small timestamp in this design is `accent-700`, not `accent`.

**Spacing** (0.85× density, already baked in) — `--space-1: 3.4px`, `-2: 6.8px`, `-3: 10.2px`, `-4: 13.6px`, `-6: 20.4px`, `-8: 27.2px`.

**Radius** — `--radius-sm/md/lg` exist but **`.card`, `.btn`, `.input`, `.tag`, `.seg`, `.dialog` are all overridden to `0`**. Keep it that way.

**Type** — `--font-heading: "Barlow Condensed"`, `--font-body: "Barlow"`, heading weight 600. Base body 15px / `line-height: 1.55`. Headings: `h1 42` · `h2 32` · `h3 25` · `h4 20` · `h5 16` · `h6 13` (uppercase, `0.08em`), all `line-height: 1.12`, `letter-spacing: -0.015em`.

**Shadows** — `--shadow-sm/md/lg`. Only `.elev-md` is used (on the toast).

**Tabular numerals** — every timestamp, score, count, and duration uses `font-variant-numeric: tabular-nums`. Don't skip this; the design has a lot of numbers in columns.

### Dark mode

Implemented as `:root[data-theme="dark"]` token overrides (see the `<style>` block at the top of the prototype — **copy it into your stylesheet verbatim**). The approach: **the tonal ramps invert**. `--color-accent-100` becomes the darkest step and `--color-accent-900` the lightest, so every existing usage — tinted fill at a low step, text on it at a high step — keeps its contrast relationship with zero markup changes. `--color-accent` lifts to the `500` step (`#749dc4`) so it still reads against the dark ground, per the system's guidance to go one step lighter on dark.

Ground: `--color-bg: #1d1f20`, `--color-surface: #2b2b2d`, `--color-text: #f2f2f3`, `--color-divider: color-mix(in srgb, #f2f2f3 22%, transparent)`. Shadows get deeper and more ambient.

Toggle it by setting `data-theme="dark"` on `<html>`; persist to `localStorage['grasp-theme']`. Consider defaulting from `prefers-color-scheme` when nothing is stored — the prototype defaults to light.

## Assets

- **Fonts** — Barlow and Barlow Condensed, `@import`ed from Google Fonts at the top of `industry.css`. For production, self-host or add `<link rel="preconnect">` to avoid the render delay.
- **Icons** — [Lucide](https://lucide.dev) at `stroke-width="1.5"`. Only `sun` and `moon` are used so far (inlined as SVG in the prototype). Install `lucide-react` for anything further; do not mix in another icon set or a heavier stroke.
- **Images** — none. Video thumbnails come from `videos.thumbnail_url`. The diagonal-hatch blocks in the prototype are placeholders for the thumbnail and the YouTube iframe.
- No logo asset exists; the brand is the wordmark `GRASP` set in Barlow Condensed.

## Gaps against the current codebase

Two things in this design have no backing in the repo. Both are intentional; decide before you build.

1. **No per-card grading in flashcard review.** There's no review-state or scheduling table in the schema, so the deck is a browser (reveal + previous/next), not a spaced-repetition system. If you want "got it / needs work", that's a new table and new endpoints — out of scope here.
2. **The two-column workspace is new.** `VideoDetailPage.tsx` is currently a single vertical column with everything stacked, and flashcards/quizzes open as modals (`FlashcardConfigModal`, `QuizConfigModal`). This design moves them into a persistent right-hand tab panel so the player stays visible. That's a restructure of `VideoDetailPage`, and the two `*ConfigModal` components become inline panel views. The modal-specific wrappers can go; their form logic carries over.

Everything else — statuses, field names, config payloads, grading semantics, the `grounded: false` case, the broad-vs-specific source split — traces to `docs/DATA_MODEL.md`, `docs/API.md`, or the existing components.

## Files

| Path | What it is |
|---|---|
| `design/Grasp - Study Companion.dc.html` | The prototype. Open in a browser; all five surfaces are interactive. Markup at the top, state logic in the `class Component` at the bottom. |
| `design/industry.css` | The Industry design system — tokens and component classes. **Copy this into the web client.** |
| `design/support.js` | Prototype runtime only. **Do not port.** |

Source references in the repo: `docs/DATA_MODEL.md`, `docs/API.md`, `docs/ARCHITECTURE.md`, and `web/src/` (`pages/VideoDetailPage.tsx`, `components/ChatPanel.tsx`, `components/FlashcardReview.tsx`, `components/QuizTake.tsx`, `components/QuizResults.tsx`, `components/VideoList.tsx`, `lib/time.ts`).
