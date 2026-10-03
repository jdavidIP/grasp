# Video workspace shell — design

Sub-project 2 of 5 for [#24](https://github.com/jdavidIP/grasp/issues/24). The decisions for the whole issue are recorded in `2026-10-03-ui-foundation-library-design.md`. Sub-project 1 (#45) shipped the design system, header, theme, toasts and Library.

## Scope

Restructure `VideoDetailPage` from one stacked column into the handoff's two-column workspace (handoff §3):
- **Left column:** player, title and topics.
- **Right column:** a persistent tabbed Chat / Flashcards / Quizzes panel.

Fix repeated seeks along the way. The tab *contents* move in as they are; their restyles, including the config modals becoming in-panel views, are sub-projects 3–5.

## 1. Layout and left column

`VideoDetailPage.css` holds the screen's layout, using `.workspace-*` classes and Industry tokens only.

- **Page:** max-width 1460px, centered, padding `clamp(16px,2.5vw,26px) clamp(14px,3vw,28px) 56px`.
- **Back button:** `← Library` as `.btn .btn-secondary`, a react-router `Link`, with `margin-bottom: var(--space-4)`.
- **Columns:** `display: flex; flex-wrap: wrap; gap: clamp(20px,2.2vw,30px); align-items: flex-start`.
  - Left: `flex: 1 1 520px; min-width: 0`, a column with `gap: var(--space-6)`.
  - Right: `flex: 1 1 430px; min-width: 0`.
  - The columns stack on narrow viewports.
- **Loading / error:** "Loading…" muted, and a fetch error inline with `role="alert"`, both in the page body.
- **Title row:**
  - `<h2>` with the title.
  - Below it, a muted 13px tabular line: the parts that exist among `channel`, `formatTime(duration_seconds)` and "{n} segments" (singular "1 segment"), joined with " · ". Null parts are omitted, so "null" never prints.
  - Right-aligned in the same row: the status `.tag` (same classes as the Library: `ready` uses `tag-accent`, `failed` uses `tag-outline`, `pending`/`processing` use `tag-neutral`; uppercase), and a **Reprocess** `.btn .btn-secondary`. Reprocess is hidden while `pending`/`processing`, as today. A reprocess error shows inline with `role="alert"`.
  - When `failed`, the `error_message` shows below the row with `role="alert"` in `--color-accent-800`.
- **Player:** only when `status === 'ready'`.
  - `<figure className="blueprint workspace-player">` with the four corner marks and `aspect-ratio: 16/9`, wrapping `YouTubePlayer`.
  - The player's wrapper and the YouTube iframe fill the figure: width and height 100%. Today the embed uses YouTube's fixed default size.
- **Topics (`TopicList`):**
  - A header row, `<h6>Topics</h6>` and `<h6 class="text-muted">{n} segments</h6>`, over a hairline.
  - Each segment is a `<button type="button">` row, so it's keyboard reachable, with the handoff's look and the 4% hover. It shows:
    - `formatTime(start)–formatTime(end)` in 12.5px tabular `--color-accent-700`, min-width 92px;
    - the label in Barlow Condensed 600 16px;
    - the summary in muted 13px.
  - Clicking calls `seek(start_time)`.
  - With no segments: "No topics yet." (muted).

## 2. Tabbed panel (`WorkspaceTabs`)

- **Frame:** `.blueprint` with corner marks, `background: var(--color-bg)`, `height: min(80vh, 840px)`, `display: flex; flex-direction: column`.
- **Tab strip:**
  - `role="tablist"` (labelled "Study tools").
  - Three `role="tab"` buttons: Chat, Flashcards, Quizzes. Each is `flex: 1`, padding `var(--space-3)`, with a right hairline, Barlow Condensed 600 15px and `letter-spacing: 0.02em`.
  - Active: `background: var(--color-accent); color: var(--color-bg)`. Inactive: transparent on `--color-text`.
  - The strip has a bottom hairline.
- **Panels:**
  - Each is a `role="tabpanel"` with `aria-labelledby` pointing at its tab, inside one scroll region: `flex: 1; min-height: 0; overflow-y: auto; padding: var(--space-6)`.
  - **All three panels stay mounted; inactive ones get the `hidden` attribute.** A half-taken quiz, a typed chat question, the flashcard position and the scroll position all survive switching. (User decision: option A.)
- **Keyboard:** roving tabindex. Only the active tab has `tabIndex=0`. ArrowRight/ArrowLeft move and wrap, Home and End jump to the first and last, and each also activates and focuses the tab.
- **URL:** the active tab is synced to `?tab=chat|flashcards|quizzes` via `useSearchParams`.
  - A missing or invalid value means `chat`.
  - Switching uses `replace: true`, so Back leaves the page rather than stepping through tabs.
  - Other search params are preserved.
- **Panel contents:** today's sections as they are.
  - **Chat:** `ChatPanel`.
  - **Flashcards:** `FlashcardConfigModal`, `FlashcardDeckList`, and `FlashcardReview` when a deck is open.
  - **Quizzes:** `QuizConfigModal`, `QuizList`, and `QuizTake` / `QuizAttemptHistory` when a quiz is open.

  The existing per-section state (`reviewingDeckId`, `activeQuiz`) and the props they pass stay as they are.
- **Not ready:** when `status !== 'ready'`, the right column shows the same frame without tabs, holding a muted note:
  - `pending` / `processing`: "Chat, flashcards and quizzes open once the video is processed."
  - `failed`: "This video couldn't be processed. Reprocess it to use chat, flashcards and quizzes."

  `useVideoQuery` already polls every 1.5s while in progress, so the panel appears on its own once the video is ready.

## 3. Seeking

- **Problem:** today `seekSeconds: number | null` is passed to the player, which seeks in an effect keyed on the number. Seeking to the same time twice changes nothing, so the second click is ignored. With topic rows, re-clicking a topic after watching on is routine.
- **Fix:**
  - The page holds `seekRequest: { seconds: number; id: number } | null`.
  - `seek(seconds)` sets `{ seconds, id: previous id + 1 }` and shows the toast "Jumped to {formatTime(seconds)}".
  - `YouTubePlayer` takes `seek: SeekRequest | null` instead of `seekSeconds`. Its effect is keyed on the request object, so every request seeks. `null` means nothing has been sought yet.
  - The type `SeekRequest` is exported from `YouTubePlayer.tsx`.
- **Callers:** every caller that took `onSeek: (seconds: number) => void` (`ChatPanel`, `FlashcardReview`, `QuizTake`, `QuizAttemptHistory`, `TopicList`) receives `seek`. Their signatures don't change.
- **Known limit:** a seek issued before the YouTube player has finished loading is dropped, as today, but its toast still shows. It's left as is because it can only happen in the first moment after the page loads.

## Files

| File | Change |
|---|---|
| `web/src/pages/VideoDetailPage.tsx` | Rewritten as the shell: title row, player, topics, tabbed panel, seek state. |
| `web/src/pages/VideoDetailPage.css` | New: `.workspace-*` layout. |
| `web/src/components/WorkspaceTabs.tsx` + `.css` | New: tablist/tabpanels, keyboard, `?tab=` sync, mounted-but-hidden panels. |
| `web/src/components/TopicList.tsx` | New: topics header and seek rows. Styles go in `VideoDetailPage.css`, since only that page uses them. |
| `web/src/components/YouTubePlayer.tsx` | `seek: SeekRequest \| null` replaces `seekSeconds`; the wrapper fills its container. |

## Testing

Vitest + React Testing Library:
- **`WorkspaceTabs`:**
  - roles, `aria-selected` and `aria-controls`/`labelledby`;
  - ArrowRight, ArrowLeft (wrapping), Home and End move selection and focus;
  - inactive panels are `hidden` but mounted: text typed into an input in one panel survives switching away and back;
  - `?tab=quizzes` selects Quizzes on load, an invalid value falls back to Chat, and switching updates the param.
- **`YouTubePlayer`:** with a fake IFrame API, two requests for the same seconds call `seekTo` twice. The existing #25 regression test keeps passing.
- **`TopicList`:** a click calls `seek` with the segment's `start_time`. The empty state.
- **`VideoDetailPage`** (fetch stubbed):
  - the title row with null channel and null duration prints no "null";
  - the segment count is singular for 1;
  - the processing and failed notes appear instead of tabs;
  - clicking a topic shows the "Jumped to …" toast.

Plus `typecheck`, `lint`, `build` and `npm test`.

**Manual browser check** against the prototype in light and dark mode, and at a narrow width (stacked):
- the player fills the frame;
- topics seek, including the same topic twice;
- tabs work by keyboard and keep their state;
- `?tab=` survives a reload;
- the processing and failed notes show;
- chat, flashcards and quizzes still work inside the tabs.

## Out of scope

- Restyling the tab contents and replacing the config modals (sub-projects 3–5).
- The scrub row (dropped for #24).
- Seeking before the player has loaded.
