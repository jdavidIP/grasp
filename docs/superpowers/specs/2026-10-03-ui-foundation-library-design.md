# UI foundation + Library — design

Sub-project 1 of 5 for [#24](https://github.com/jdavidIP/grasp/issues/24): apply the Industry design system and restructure the video workspace.

## Context

#24 applies the "Industry" design handoff (README, `industry.css`, an interactive HTML prototype) to the web client, and restructures the video page into a two-column workspace with a tabbed Chat / Flashcards / Quizzes panel. The handoff is high-fidelity: tokens, sizes and behavior are final. The portfolio thesis is still retrieval and generation quality, so the UI should present it well without growing into its own project.

### Decisions already made for #24 as a whole

| Topic | Decision |
|---|---|
| Delivery | Five sub-projects, each with its own spec, plan and PR referencing #24. The last PR closes it. |
| 1. Foundation + Library | This spec. |
| 2. Workspace shell | Two columns, accessible tabs, topics list, player. |
| 3. Chat tab | Includes the **full** sources-on-reload fix: store what's needed to rebuild sources for every answer (specific, broad, and the `grounded` flag), via a schema change, migration and the history endpoint returning sources. |
| 4. Flashcards tab | Deck list, inline config, generating view, review. |
| 5. Quizzes tab | List, inline config, take, results, history. |
| Chat suggestion chips | Dropped. The API has no source for them. |
| Ingestion "current stage" note | Dropped. The API has only `status`, so processing videos show a generic note. |
| Scrub row under the player | Dropped. It would duplicate the embedded player's own progress bar. |
| Per-card flashcard grading | Out of scope (CLAUDE.md: no spaced repetition). |
| App-specific styles | Plain CSS files next to each screen, class names prefixed by screen (e.g. `.library-row`), values only from Industry tokens. Not CSS Modules, not inline styles. |

## Scope of this sub-project

Design system foundation, app shell (header, theme, toasts) and the Library page. The video page keeps its current layout until sub-project 2. It will pick up the new base styles, which is acceptable in between.

## 1. Styles and the copied handoff

- **`docs/design/`** gets the handoff's `README.md` and `industry.css`, so the work is reproducible from a clean checkout. The prototype HTML and `support.js` are not copied: the prototype only opens with that runtime, which the handoff says not to port.
- **`web/src/styles/industry.css`**: a verbatim copy, imported once from `main.tsx`. Kept verbatim so differences from the design system stay visible. App overrides go elsewhere.
- **`web/src/index.css`**: the Vite starter theme is deleted and replaced with:
  - the prototype's `:root[data-theme="dark"]` block, copied verbatim (the handoff says to);
  - base rules: `body` background, text and font from tokens;
  - a `.tabular` helper (`font-variant-numeric: tabular-nums`).

  The starter's fixed-width centered `#root` goes; each page sets its own width.
- **`index.html`**:
  - The title becomes "Grasp".
  - It gets a `preconnect` for Google Fonts.
  - It gets a small inline script that applies the stored or system theme to `<html data-theme>` before first paint, so a dark-mode reload doesn't flash light.

## 2. App shell

### Theme — `web/src/lib/theme.ts`
- `initialTheme()`: `localStorage['grasp-theme']` if it's `'light'` or `'dark'`. Otherwise `prefers-color-scheme: dark` gives `'dark'`, and anything else gives `'light'`. Storage access is wrapped in try/catch, so blocked storage falls back to the system preference.
- `useTheme()` returns `[theme, toggle]`. It sets or removes `data-theme="dark"` on `<html>` and persists to `localStorage['grasp-theme']`.
- The inline script in `index.html` duplicates `initialTheme`'s rule (a few lines). It has to run before the bundle loads. A comment in each place points to the other.

### Header — `web/src/components/AppHeader.tsx` (+ `AppHeader.css`)
- Follows handoff §1: sticky, hairline bottom border, `.nav` inner wrapper at max-width 1460px.
- The `GRASP` brand (`.nav-brand`) links to `/`.
- A muted, uppercase, tabular `meta` string comes in as a prop.
- The theme toggle is a `.btn .btn-icon` with an inline SVG sun/moon (Lucide paths, stroke 1.5). Its `aria-label` names the theme it switches to.
- No `lucide-react` dependency yet; add it when a later sub-project needs more icons.
- Each page renders its own header and passes `meta`: the Library passes "{n} videos". The video page passes its `youtube_id` once it's restyled in sub-project 2; until then it renders the header with that meta and is otherwise unchanged.

### Toasts — `web/src/components/Toast.tsx` (+ `Toast.css`)
- `ToastProvider` wraps the app in `main.tsx`.
- `useToast()` returns `show(message: string)`.
- One message at a time; a new message replaces the current one and restarts the timer. Cleared after 1900ms.
- Styled per the handoff's Interactions table: fixed bottom-center, 28px up, `.blueprint .elev-md` with corner marks, accent background, `--color-bg` text, 13px tabular.
- Rendered in a `role="status"` `aria-live="polite"` region.
- Used here for "Video added — processing" (add success) and "Video deleted" (delete success). Errors stay inline, next to the action, with `role="alert"` (handoff: Errors).

## 3. Library page

Follows handoff §2. `LibraryPage.css` holds the screen's layout.

- **Container:** max-width 1020px, centered, padding per the handoff.
- **Heading:** `<h1>Library</h1>`, plus the prototype's intro paragraph in `.text-muted`, max 58ch: "Add a YouTube URL. Grasp fetches the transcript, splits it into topic segments, embeds the chunks, and then every answer, card and question can point back to a timestamp."
- **Add row (`AddVideoForm`):**
  - `.input` (keeps `type="url"` and `required`), plus `.btn .btn-primary .blueprint` "Add video" with corner marks.
  - Enter submits (it's a form). While pending, the button is disabled and reads "Adding…".
  - Errors show the API's `detail` inline (`role="alert"`, `--color-accent-800`). The API's 409 text is already user-facing ("This video is already in the library."), so no special mapping.
- **List header:** `<h6>{n} videos</h6>` and `<h6 class="text-muted">Newest first</h6>` over a hairline. The API already orders by `created_at desc`.
- **Row (`VideoList`):**
  - The thumbnail and the text block form one `<Link>` to `/videos/{id}`. Delete sits outside the link, so it can't trigger navigation.
  - **Thumbnail:** 124×70, hairline border, `object-fit: cover`. A diagonal-hatch block if there's no `thumbnail_url`. A duration badge bottom-right when `duration_seconds` is known.
  - **Title:** Barlow Condensed 600 19px.
  - **Sub-line:** "{channel} · added {relative time}", muted 13px. The channel part is omitted when null.
  - **Note line:**
    - `failed`: `error_message` with `role="alert"` in `--color-accent-800`.
    - `pending` / `processing`: muted "Processing — this can take a few minutes for long videos."
    - `ready`: none.
  - **Status tag:** the raw enum value, uppercase. `ready` uses `.tag-accent`, `failed` uses `.tag-outline`, and `pending`/`processing` use `.tag-neutral`.
  - **Delete:** `.btn .btn-ghost` 12.5px. It keeps the existing confirm text. A delete error shows inline on that row.
  - **Hover:** 4% text tint on the row.
- **Empty state:** "No videos yet. Add one above to get started."
- **Loading:** "Loading…". A list fetch error shows inline with `role="alert"`.
- **Live status:** `useVideosQuery` already polls every 1.5s while any video is pending or processing. No change.

### Helpers — `web/src/lib/time.ts`
- `formatTime(seconds)` gains hours. Under an hour it's `m:ss` as today; from an hour up it's `h:mm:ss`. This also fixes every existing timestamp past an hour, e.g. the 3-hour podcast's "182:45".
- `formatRelative(iso, now = new Date())` uses `Intl.RelativeTimeFormat('en', { numeric: 'auto' })`. It picks the largest fitting unit from seconds up to years, giving "just now", "5 minutes ago", "yesterday", and so on. No date library.

## Testing

Vitest + React Testing Library, as set up in #27:
- `theme.ts`:
  - A stored value wins.
  - With nothing stored, it follows `prefers-color-scheme` (stubbed `matchMedia`).
  - Toggling flips `data-theme` and persists it.
  - Unusable storage falls back to the system preference.
- `time.ts`:
  - `formatTime` at 0, 59, 61, 3599, 3600 and 10965 seconds.
  - `formatRelative` across unit boundaries, with a fixed `now`.
- `VideoList`: per status, the tag text and class, the note line, and `role="alert"` for `failed`. Delete is outside the row link.
- `Toast`: shows a message; a second message replaces the first; it clears after 1900ms (fake timers).

`typecheck`, `lint`, `build` and `npm test` must pass.

**Manual check in the browser:** the Library and header in light and dark, compared against the prototype. That covers spacing, type, corner marks, hover, focus ring, and a reload in dark mode with no light flash. Pixel fidelity isn't something unit tests catch.

## Out of scope here

- The video page restructure (sub-project 2) and the three tabs (3–5).
- `lucide-react`.
- Self-hosting the fonts. They stay as Google Fonts `@import`s with a preconnect, which the handoff accepts.
