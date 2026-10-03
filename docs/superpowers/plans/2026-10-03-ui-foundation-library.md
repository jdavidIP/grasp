# UI Foundation + Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the Industry design system, the app shell (header, theme, toasts) and a restyled Library page in place: sub-project 1 of 5 for #24.

**Architecture:**
- `industry.css` is copied verbatim and imported globally. `index.css` holds only the dark-mode overrides and app-wide base rules.
- Each screen gets a plain CSS file next to it, with class names prefixed by the screen, using Industry tokens only.
- Theme state lives in `lib/theme.ts`, plus an inline pre-paint script in `index.html`.
- Toasts are a small React context.

**Tech Stack:** React 19, TypeScript (strict), Vite 8, TanStack Query 5, react-router 8, Vitest 5 + React Testing Library + jsdom (Node 24 container).

**Spec:** `docs/superpowers/specs/2026-10-03-ui-foundation-library-design.md`

## Global Constraints

- **Branch:** `feat/24-industry-design-system`. One commit per task. **Before each commit, show the change and wait for the user's go-ahead** (`CLAUDE_WORKFLOW.md`). No `Co-Authored-By` trailer. Conventional messages ending with `Refs #24`.
- **Running commands:** every web command runs in the container: `docker compose exec -T web <cmd>`. From Git Bash, prefix with `MSYS_NO_PATHCONV=1` when passing container paths.
- **No new runtime dependencies:** no `lucide-react`, no date library, no CSS tooling.
- **Values:** take colors, spacing and type from Industry tokens (`var(--…)`). Don't hard-code a hex or px the tokens already carry. The handoff's literal sizes (e.g. 124×70, 19px, 12.5px) are fine.
- **Tests:** import from `'vitest'` explicitly. `globals: true` exists only for React Testing Library cleanup.
- **TypeScript:** no `any`, strict mode.
- **Fixed copy:**
  - Intro: "Add a YouTube URL. Grasp fetches the transcript, splits it into topic segments, embeds the chunks, and then every answer, card and question can point back to a timestamp."
  - Processing note: "Processing — this can take a few minutes for long videos."
  - Empty state: "No videos yet. Add one above to get started."
  - Toasts: "Video added — processing", "Video deleted".
  - localStorage key: `grasp-theme`. Toast duration: `1900` ms.

## Review Focus

1. **A video with no thumbnail, no channel or no duration** (null fields). The row renders the hatch fallback, omits "{channel} · ", and omits the duration badge, rather than printing "null". Tested in Task 6.
2. **Storage blocked** (privacy mode throws on `localStorage`). The theme falls back to the system preference and toggling still works for the session. Tested in Task 2.
3. **Toggling the theme on one page, then navigating.** The other page's header reads the saved value, so the theme stays consistent. Covered because `initialTheme()` reads storage on mount; asserted in Task 2's persistence test.
4. **Two toasts in quick succession** (add a video, then delete one within 1.9s). The second replaces the first, and the timer restarts so the second isn't cut short. Tested in Task 4.
5. **A video over an hour long.** The duration badge shows `h:mm:ss`, not `182:45`. Tested in Task 5.

---

## File Structure

| File | Responsibility |
|---|---|
| `docs/design/README.md`, `docs/design/industry.css` | Verbatim handoff copies (reference). |
| `web/src/styles/industry.css` | Verbatim design system, imported once. |
| `web/src/index.css` | Dark-mode token overrides, `.tabular`, legacy `.status-failed` (still used by the video and chat screens until sub-projects 2–3). |
| `web/index.html` | Title, font preconnect, pre-paint theme script. |
| `web/src/lib/theme.ts` | `Theme`, `THEME_KEY`, `initialTheme()`, `applyTheme()`, `useTheme()`. |
| `web/src/components/AppHeader.tsx` + `.css` | Sticky header: brand link, meta text, theme toggle. |
| `web/src/components/Toast.tsx` + `.css` | `ToastProvider`, `useToast()`. |
| `web/src/lib/time.ts` | `formatTime` (now with hours), `formatRelative`. |
| `web/src/pages/LibraryPage.tsx` + `.css` | Library layout and copy. All `.library-*` classes live here. |
| `web/src/components/AddVideoForm.tsx` | Restyled add row and a success toast. |
| `web/src/components/VideoList.tsx` | Restyled rows and a delete toast. |
| `web/src/pages/VideoDetailPage.tsx` | Gains `<AppHeader>` only. |

---

### Task 1: Copy the handoff into the repo

**Files:**
- Create: `docs/design/README.md` (copy of `~/Downloads/design_handoff_grasp_ui/README.md`)
- Create: `docs/design/industry.css` (copy of `~/Downloads/design_handoff_grasp_ui/design/industry.css`)

**Interfaces:** Consumes nothing. Produces the reference files later tasks cite.

- [ ] **Step 1: Copy both files verbatim**

```bash
mkdir -p docs/design
cp ~/Downloads/design_handoff_grasp_ui/README.md docs/design/README.md
cp ~/Downloads/design_handoff_grasp_ui/design/industry.css docs/design/industry.css
```

- [ ] **Step 2: Verify they're byte-identical**

Run: `cmp ~/Downloads/design_handoff_grasp_ui/README.md docs/design/README.md && cmp ~/Downloads/design_handoff_grasp_ui/design/industry.css docs/design/industry.css && echo identical`
Expected: `identical`

- [ ] **Step 3: Show the user, wait for approval, commit**

```bash
git add docs/design/README.md docs/design/industry.css
git commit -m "docs: copy the Industry design handoff into the repo

README and industry.css from the handoff, so #24 is reproducible from
a clean checkout. The prototype and its runtime stay out.

Refs #24"
```

---

### Task 2: Design system, base styles and theme

**Files:**
- Create: `web/src/styles/industry.css` (verbatim copy of `docs/design/industry.css`)
- Replace: `web/src/index.css`
- Modify: `web/src/main.tsx` (import order)
- Modify: `web/index.html`
- Create: `web/src/lib/theme.ts`
- Test: `web/src/lib/theme.test.ts`

**Interfaces:**
- Produces:
  - `type Theme = 'light' | 'dark'`
  - `const THEME_KEY = 'grasp-theme'`
  - `initialTheme(): Theme`
  - `applyTheme(theme: Theme): void`
  - `useTheme(): [Theme, () => void]`

- [ ] **Step 1: Write the failing tests** (`web/src/lib/theme.test.ts`)

```ts
import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { THEME_KEY, initialTheme, useTheme } from './theme'

function stubSystemDark(dark: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: dark && query === '(prefers-color-scheme: dark)',
  }))
}

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

it('uses the stored theme over the system preference', () => {
  stubSystemDark(true)
  localStorage.setItem(THEME_KEY, 'light')
  expect(initialTheme()).toBe('light')
})

it('follows the system preference when nothing is stored', () => {
  stubSystemDark(true)
  expect(initialTheme()).toBe('dark')
  stubSystemDark(false)
  expect(initialTheme()).toBe('light')
})

it('ignores a stored value that is not a theme', () => {
  stubSystemDark(false)
  localStorage.setItem(THEME_KEY, 'purple')
  expect(initialTheme()).toBe('light')
})

it('falls back to the system preference when storage is blocked', () => {
  stubSystemDark(true)
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  expect(initialTheme()).toBe('dark')
})

it('toggles data-theme on <html> and persists the choice', () => {
  stubSystemDark(false)
  const { result } = renderHook(() => useTheme())
  expect(document.documentElement.getAttribute('data-theme')).toBeNull()

  act(() => result.current[1]())
  expect(result.current[0]).toBe('dark')
  expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  expect(localStorage.getItem(THEME_KEY)).toBe('dark')

  // A header mounted later (another page) starts from the saved choice.
  expect(renderHook(() => useTheme()).result.current[0]).toBe('dark')
})

it('still toggles for the session when storage is blocked', () => {
  stubSystemDark(false)
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  const { result } = renderHook(() => useTheme())
  act(() => result.current[1]())
  expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `docker compose exec -T web npx vitest run src/lib/theme.test.ts`
Expected: FAIL, because `./theme` can't be resolved.

- [ ] **Step 3: Implement `web/src/lib/theme.ts`**

```ts
import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

export const THEME_KEY = 'grasp-theme'

// index.html inlines this same rule so the theme applies before first paint; keep the
// two in sync.
export function initialTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    // Storage blocked (privacy mode): fall back to the system preference.
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyTheme(theme: Theme): void {
  if (theme === 'dark') document.documentElement.setAttribute('data-theme', 'dark')
  else document.documentElement.removeAttribute('data-theme')
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(initialTheme)

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  function toggle() {
    const next: Theme = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    try {
      localStorage.setItem(THEME_KEY, next)
    } catch {
      // Storage blocked: the choice still applies for this session.
    }
  }

  return [theme, toggle]
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose exec -T web npx vitest run src/lib/theme.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 5: Copy the design system and replace the base stylesheet**

```bash
mkdir -p web/src/styles
cp docs/design/industry.css web/src/styles/industry.css
```

Replace `web/src/index.css` entirely with:

```css
/* App-wide additions on top of styles/industry.css. Screen layout lives in a CSS
   file next to each screen. */

/* Dark theme, copied verbatim from the design handoff's prototype: the ramps invert
   on a shared lightness scale, so every existing token usage (tinted fill = low step,
   text on it = high step) keeps its contrast relationship without touching markup. */
:root[data-theme="dark"] {
  --color-bg: #1d1f20;
  --color-surface: #2b2b2d;
  --color-text: #f2f2f3;
  --color-divider: color-mix(in srgb, #f2f2f3 22%, transparent);
  --color-accent: #749dc4;
  --color-accent-2: #7e9cb8;

  --color-neutral-100: #2b2b2d;
  --color-neutral-200: #323234;
  --color-neutral-300: #424244;
  --color-neutral-400: #5d5d60;
  --color-neutral-500: #7a7a7d;
  --color-neutral-600: #98989b;
  --color-neutral-700: #b7b7ba;
  --color-neutral-800: #d4d4d7;
  --color-neutral-900: #f5f5f8;

  --color-accent-100: #1d2d3d;
  --color-accent-200: #2c455d;
  --color-accent-300: #416180;
  --color-accent-400: #597ea3;
  --color-accent-500: #749dc4;
  --color-accent-600: #94bce3;
  --color-accent-700: #b5d9fd;
  --color-accent-800: #d6ebff;
  --color-accent-900: #eef6ff;

  --color-accent-2-100: #1f2d3a;
  --color-accent-2-200: #314457;
  --color-accent-2-300: #486077;
  --color-accent-2-400: #627d98;
  --color-accent-2-500: #7e9cb8;
  --color-accent-2-600: #9ebbd8;
  --color-accent-2-700: #bdd8f2;
  --color-accent-2-800: #d6ebff;
  --color-accent-2-900: #eef6ff;

  --shadow-sm: 0 1px 2px color-mix(in srgb, #000 55%, transparent);
  --shadow-md: 0 3px 12px color-mix(in srgb, #000 60%, transparent);
  --shadow-lg: 0 12px 34px color-mix(in srgb, #000 66%, transparent);
}
:root[data-theme="dark"] body { background: #1d1f20; color: #f2f2f3; }
:root[data-theme="dark"] input::placeholder { color: color-mix(in srgb, #f2f2f3 45%, transparent); }

body {
  min-height: 100vh;
}

.tabular {
  font-variant-numeric: tabular-nums;
}

/* Legacy: still used by the video page and chat panel until sub-projects 2-3
   restyle them. */
.status-failed {
  color: var(--color-accent-800);
}
```

In `web/src/main.tsx`, replace `import './index.css'` with:

```ts
import './styles/industry.css'
import './index.css'
```

- [ ] **Step 6: Update `web/index.html`**

Replace `<title>web</title>` with:

```html
    <title>Grasp</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <script>
      // Mirrors initialTheme() in src/lib/theme.ts. Runs before the bundle so a
      // dark-mode reload doesn't flash light. Keep the two in sync.
      ;(function () {
        var theme = null
        try {
          theme = localStorage.getItem('grasp-theme')
        } catch (e) {}
        if (theme !== 'light' && theme !== 'dark') {
          theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
        }
        if (theme === 'dark') document.documentElement.setAttribute('data-theme', 'dark')
      })()
    </script>
```

- [ ] **Step 7: Run the full checks**

Run: `docker compose exec -T web sh -c "npm test && npm run typecheck && npm run lint && npm run build"`
Expected: all pass. That's 9 tests (6 new and 3 existing), 0 lint warnings, and the build succeeds.

- [ ] **Step 8: Show the user, wait for approval, commit**

```bash
git add web/src/styles/industry.css web/src/index.css web/src/main.tsx web/index.html web/src/lib/theme.ts web/src/lib/theme.test.ts
git commit -m "feat: add the Industry design system and a persisted theme

industry.css is imported verbatim; index.css replaces the Vite starter
theme with the handoff's dark-mode tokens. The theme comes from
localStorage, else the system preference, and an inline script applies
it before first paint.

Refs #24"
```

---

### Task 3: App header

**Files:**
- Create: `web/src/components/AppHeader.tsx`, `web/src/components/AppHeader.css`
- Test: `web/src/components/AppHeader.test.tsx`

**Interfaces:**
- Consumes: `useTheme()` from `../lib/theme`.
- Produces: `AppHeader({ meta }: { meta: string })`. It must be rendered inside a router, because it uses `<Link>`.

- [ ] **Step 1: Write the failing test** (`web/src/components/AppHeader.test.tsx`)

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { AppHeader } from './AppHeader'

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
  vi.stubGlobal('matchMedia', () => ({ matches: false }))
})

afterEach(() => {
  vi.unstubAllGlobals()
})

it('links the brand home, shows the meta text, and toggles the theme', () => {
  render(
    <MemoryRouter>
      <AppHeader meta="3 videos" />
    </MemoryRouter>,
  )

  expect(screen.getByRole('link', { name: 'GRASP' }).getAttribute('href')).toBe('/')
  expect(screen.getByText('3 videos')).toBeTruthy()

  fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }))
  expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  expect(screen.getByRole('button', { name: 'Switch to light theme' })).toBeTruthy()
})
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec -T web npx vitest run src/components/AppHeader.test.tsx`
Expected: FAIL, because `./AppHeader` can't be resolved.

- [ ] **Step 3: Implement `web/src/components/AppHeader.tsx`**

```tsx
import { Link } from 'react-router'
import { useTheme } from '../lib/theme'
import './AppHeader.css'

// Lucide sun/moon paths at stroke 1.5, inlined as in the design handoff. Add
// lucide-react once more icons are needed.
function SunIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="m4.93 4.93 1.41 1.41" />
      <path d="m17.66 17.66 1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="m6.34 17.66-1.41 1.41" />
      <path d="m19.07 4.93-1.41 1.41" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
    </svg>
  )
}

export function AppHeader({ meta }: { meta: string }) {
  const [theme, toggleTheme] = useTheme()
  const label = theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'

  return (
    <header className="app-header">
      <div className="nav app-header-inner">
        <Link to="/" className="nav-brand app-header-brand">
          GRASP
        </Link>
        <span className="text-muted app-header-meta">{meta}</span>
        <button type="button" className="btn btn-icon" onClick={toggleTheme} title={label} aria-label={label}>
          {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
        </button>
      </div>
    </header>
  )
}
```

- [ ] **Step 4: Add `web/src/components/AppHeader.css`**

```css
.app-header {
  position: sticky;
  top: 0;
  z-index: 30;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-divider);
}

.app-header-inner {
  max-width: 1460px;
  margin: 0 auto;
  padding: var(--space-3) clamp(14px, 3vw, 28px);
}

.app-header-brand {
  letter-spacing: 0.02em;
}

.app-header-meta {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-variant-numeric: tabular-nums;
}
```

- [ ] **Step 5: Run it to verify it passes**

Run: `docker compose exec -T web npx vitest run src/components/AppHeader.test.tsx`
Expected: PASS.

- [ ] **Step 6: Show the user, wait for approval, commit**

```bash
git add web/src/components/AppHeader.tsx web/src/components/AppHeader.css web/src/components/AppHeader.test.tsx
git commit -m "feat: add the app header with the theme toggle

Refs #24"
```

---

### Task 4: Toasts

**Files:**
- Create: `web/src/components/Toast.tsx`, `web/src/components/Toast.css`
- Modify: `web/src/main.tsx` (wrap `<App />`)
- Test: `web/src/components/Toast.test.tsx`

**Interfaces:**
- Produces:
  - `ToastProvider({ children }: { children: ReactNode })`
  - `useToast(): (message: string) => void`. Outside a provider it's a no-op, so components stay testable without one.
  - `TOAST_MS = 1900`

- [ ] **Step 1: Write the failing tests** (`web/src/components/Toast.test.tsx`)

```tsx
import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { TOAST_MS, ToastProvider, useToast } from './Toast'

function Trigger({ message }: { message: string }) {
  const show = useToast()
  return <button onClick={() => show(message)}>{message}</button>
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

it('shows a message in a polite status region and clears it after 1900ms', () => {
  render(
    <ToastProvider>
      <Trigger message="Saved" />
    </ToastProvider>,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Saved' }))
  expect(screen.getByRole('status').textContent).toBe('Saved')

  act(() => vi.advanceTimersByTime(TOAST_MS - 1))
  expect(screen.getByRole('status').textContent).toBe('Saved')
  act(() => vi.advanceTimersByTime(1))
  expect(screen.getByRole('status').textContent).toBe('')
})

it('replaces the current message and restarts the timer', () => {
  render(
    <ToastProvider>
      <Trigger message="First" />
      <Trigger message="Second" />
    </ToastProvider>,
  )
  fireEvent.click(screen.getByRole('button', { name: 'First' }))
  act(() => vi.advanceTimersByTime(1000))
  fireEvent.click(screen.getByRole('button', { name: 'Second' }))
  expect(screen.getByRole('status').textContent).toBe('Second')

  // The first message's timer would have fired here; the second must survive it.
  act(() => vi.advanceTimersByTime(1000))
  expect(screen.getByRole('status').textContent).toBe('Second')
  act(() => vi.advanceTimersByTime(TOAST_MS - 1000))
  expect(screen.getByRole('status').textContent).toBe('')
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `docker compose exec -T web npx vitest run src/components/Toast.test.tsx`
Expected: FAIL, because `./Toast` can't be resolved.

- [ ] **Step 3: Implement `web/src/components/Toast.tsx`**

```tsx
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import './Toast.css'

export const TOAST_MS = 1900

const ToastContext = createContext<(message: string) => void>(() => {})

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null)
  const timer = useRef<number | undefined>(undefined)

  const show = useCallback((next: string) => {
    window.clearTimeout(timer.current)
    setMessage(next)
    timer.current = window.setTimeout(() => setMessage(null), TOAST_MS)
  }, [])

  useEffect(() => () => window.clearTimeout(timer.current), [])

  return (
    <ToastContext value={show}>
      {children}
      <div role="status" aria-live="polite" className="toast-region">
        {message && (
          <div className="toast blueprint elev-md">
            <i className="corner tl" />
            <i className="corner tr" />
            <i className="corner bl" />
            <i className="corner br" />
            {message}
          </div>
        )}
      </div>
    </ToastContext>
  )
}

export function useToast(): (message: string) => void {
  return useContext(ToastContext)
}
```

- [ ] **Step 4: Add `web/src/components/Toast.css`**

```css
.toast-region {
  position: fixed;
  left: 50%;
  bottom: 28px;
  transform: translateX(-50%);
  z-index: 50;
}

.toast {
  padding: var(--space-2) var(--space-6);
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: var(--color-bg);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
```

- [ ] **Step 5: Wrap the app in `web/src/main.tsx`**

Add `import { ToastProvider } from './components/Toast'`, and change the render tree to:

```tsx
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <App />
      </ToastProvider>
    </QueryClientProvider>
```

- [ ] **Step 6: Run the tests and checks**

Run: `docker compose exec -T web sh -c "npx vitest run src/components/Toast.test.tsx && npm run typecheck && npm run lint"`
Expected: PASS (2 tests), with typecheck and lint clean.

- [ ] **Step 7: Show the user, wait for approval, commit**

```bash
git add web/src/components/Toast.tsx web/src/components/Toast.css web/src/components/Toast.test.tsx web/src/main.tsx
git commit -m "feat: add a toast for seek and mutation confirmations

One message at a time, replaced and re-timed by the next, cleared after
1900ms, in a polite status region.

Refs #24"
```

---

### Task 5: Time formatting with hours, and relative time

**Files:**
- Modify: `web/src/lib/time.ts`
- Test: `web/src/lib/time.test.ts`

**Interfaces:**
- Produces:
  - `formatTime(seconds: number): string`. Same signature; it now handles hours.
  - `formatRelative(iso: string, now?: Date): string`

- [ ] **Step 1: Write the failing tests** (`web/src/lib/time.test.ts`)

```ts
import { expect, it } from 'vitest'

import { formatRelative, formatTime } from './time'

it('formats minutes under an hour and h:mm:ss from an hour up', () => {
  expect(formatTime(0)).toBe('0:00')
  expect(formatTime(59.9)).toBe('0:59')
  expect(formatTime(61)).toBe('1:01')
  expect(formatTime(3599)).toBe('59:59')
  expect(formatTime(3600)).toBe('1:00:00')
  expect(formatTime(10965)).toBe('3:02:45')
})

it('formats a past time relative to now in the largest fitting unit', () => {
  const now = new Date('2026-10-03T12:00:00Z')
  const ago = (seconds: number) => new Date(now.getTime() - seconds * 1000).toISOString()

  expect(formatRelative(ago(0), now)).toBe('now')
  expect(formatRelative(ago(30), now)).toBe('30 seconds ago')
  expect(formatRelative(ago(5 * 60), now)).toBe('5 minutes ago')
  expect(formatRelative(ago(3 * 3600), now)).toBe('3 hours ago')
  expect(formatRelative(ago(86400), now)).toBe('yesterday')
  expect(formatRelative(ago(3 * 86400), now)).toBe('3 days ago')
  expect(formatRelative(ago(60 * 86400), now)).toBe('2 months ago')
  expect(formatRelative(ago(400 * 86400), now)).toBe('last year')
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `docker compose exec -T web npx vitest run src/lib/time.test.ts`
Expected: FAIL. `formatTime(3600)` returns `60:00`, and `formatRelative` isn't exported.

- [ ] **Step 3: Replace `web/src/lib/time.ts`**

```ts
export function formatTime(seconds: number): string {
  const total = Math.floor(seconds)
  const hours = Math.floor(total / 3600)
  const mins = Math.floor((total % 3600) / 60)
  const secs = (total % 60).toString().padStart(2, '0')
  return hours > 0 ? `${hours}:${mins.toString().padStart(2, '0')}:${secs}` : `${mins}:${secs}`
}

const RELATIVE_UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 365 * 86400],
  ['month', 30 * 86400],
  ['week', 7 * 86400],
  ['day', 86400],
  ['hour', 3600],
  ['minute', 60],
  ['second', 1],
]

const relativeFormat = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

export function formatRelative(iso: string, now: Date = new Date()): string {
  const seconds = (new Date(iso).getTime() - now.getTime()) / 1000
  const [unit, size] = RELATIVE_UNITS.find(([, s]) => Math.abs(seconds) >= s) ?? (['second', 1] as const)
  return relativeFormat.format(Math.round(seconds / size), unit)
}
```

- [ ] **Step 4: Run them to verify they pass**

Run: `docker compose exec -T web npx vitest run src/lib/time.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the suite** (`formatTime` is used by chat, flashcards and quizzes)

Run: `docker compose exec -T web sh -c "npm test && npm run typecheck"`
Expected: all pass.

- [ ] **Step 6: Show the user, wait for approval, commit**

```bash
git add web/src/lib/time.ts web/src/lib/time.test.ts
git commit -m "feat: show hours in timestamps and add relative time

formatTime gave 182:45 for a 3-hour podcast; it now gives h:mm:ss from
an hour up. formatRelative uses Intl.RelativeTimeFormat, no library.

Refs #24"
```

---

### Task 6: Restyled Library page

**Files:**
- Modify: `web/src/pages/LibraryPage.tsx`
- Create: `web/src/pages/LibraryPage.css`
- Modify: `web/src/components/AddVideoForm.tsx`
- Modify: `web/src/components/VideoList.tsx`
- Modify: `web/src/pages/VideoDetailPage.tsx` (add the header only)
- Test: `web/src/components/VideoList.test.tsx`

**Interfaces:**
- Consumes:
  - `AppHeader({ meta })` (Task 3)
  - `useToast()` (Task 4)
  - `formatTime`, `formatRelative` (Task 5)
  - `useVideosQuery`, `useCreateVideo`, `useDeleteVideo` (existing)
  - `VideoListItem` (existing type)
- Produces: `VideoList({ videos }: { videos: VideoListItem[] })`. The signature is unchanged.

- [ ] **Step 1: Write the failing tests** (`web/src/components/VideoList.test.tsx`)

```tsx
import { screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { expect, it } from 'vitest'

import { renderWithClient } from '../test/render'
import type { VideoListItem } from '../types/video'
import { VideoList } from './VideoList'

function video(overrides: Partial<VideoListItem>): VideoListItem {
  return {
    id: 'v1',
    youtube_id: 'abc',
    title: 'A lecture',
    channel: 'Yale Courses',
    duration_seconds: 10965,
    thumbnail_url: 'https://img/v1.jpg',
    status: 'ready',
    error_message: null,
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

function renderList(videos: VideoListItem[]) {
  return renderWithClient(
    <MemoryRouter>
      <VideoList videos={videos} />
    </MemoryRouter>,
  )
}

it('renders a ready video with its tag, duration, channel line and no note', () => {
  renderList([video({})])
  const row = screen.getByRole('listitem')
  const tag = within(row).getByText('ready')
  expect(tag.className).toContain('tag-accent')
  expect(within(row).getByText('3:02:45')).toBeTruthy()
  expect(within(row).getByText(/^Yale Courses · added /)).toBeTruthy()
  expect(within(row).queryByRole('alert')).toBeNull()
  expect(within(row).queryByText(/Processing/)).toBeNull()
})

it('shows the error as an alert for a failed video', () => {
  renderList([video({ status: 'failed', error_message: 'No transcript available.' })])
  expect(screen.getByText('failed').className).toContain('tag-outline')
  expect(screen.getByRole('alert').textContent).toBe('No transcript available.')
})

it.each(['pending', 'processing'] as const)('shows the generic processing note while %s', (status) => {
  renderList([video({ status })])
  expect(screen.getByText(status).className).toContain('tag-neutral')
  expect(
    screen.getByText('Processing — this can take a few minutes for long videos.'),
  ).toBeTruthy()
})

it('handles a video with no thumbnail, channel or duration', () => {
  renderList([video({ thumbnail_url: null, channel: null, duration_seconds: null })])
  const row = screen.getByRole('listitem')
  expect(within(row).queryByRole('img')).toBeNull()
  expect(within(row).getByText(/^added /)).toBeTruthy()
  expect(row.textContent).not.toContain('null')
})

it('keeps Delete outside the link to the video', () => {
  renderList([video({})])
  const link = screen.getByRole('link')
  expect(link.getAttribute('href')).toBe('/videos/v1')
  expect(within(link).queryByRole('button')).toBeNull()
  expect(screen.getByRole('button', { name: 'Delete' })).toBeTruthy()
})

it('shows the empty state', () => {
  renderList([])
  expect(screen.getByText('No videos yet. Add one above to get started.')).toBeTruthy()
})
```

The thumbnail `<img>` uses `alt=""`, so it has no `img` role. The no-thumbnail test therefore passes either way on that line. The other two lines are what guard the null fields.

- [ ] **Step 2: Run them to verify they fail**

Run: `docker compose exec -T web npx vitest run src/components/VideoList.test.tsx`
Expected: FAIL. There's no duration badge, no tag classes and no channel line yet.

- [ ] **Step 3: Rewrite `web/src/components/VideoList.tsx`**

```tsx
import { Link } from 'react-router'
import { useDeleteVideo } from '../hooks/useVideos'
import { formatRelative, formatTime } from '../lib/time'
import type { VideoListItem } from '../types/video'
import { useToast } from './Toast'

interface VideoListProps {
  videos: VideoListItem[]
}

const TAG_CLASS: Record<VideoListItem['status'], string> = {
  ready: 'tag-accent',
  failed: 'tag-outline',
  pending: 'tag-neutral',
  processing: 'tag-neutral',
}

export function VideoList({ videos }: VideoListProps) {
  const deleteVideo = useDeleteVideo()
  const toast = useToast()

  if (videos.length === 0) {
    return <p className="text-muted library-empty">No videos yet. Add one above to get started.</p>
  }

  function handleDelete(video: VideoListItem) {
    if (
      !window.confirm(
        `Delete "${video.title}"? This removes its chat history, flashcards, and quizzes too, and cannot be undone.`,
      )
    ) {
      return
    }
    deleteVideo.mutate(video.id, { onSuccess: () => toast('Video deleted') })
  }

  return (
    <ul className="library-list">
      {videos.map((video) => (
        <li key={video.id} className="library-row">
          <Link to={`/videos/${video.id}`} className="library-row-link">
            <span className="library-thumb">
              {video.thumbnail_url && <img src={video.thumbnail_url} alt="" />}
              {video.duration_seconds !== null && (
                <span className="library-duration tabular">{formatTime(video.duration_seconds)}</span>
              )}
            </span>
            <span className="library-text">
              <span className="library-title">{video.title}</span>
              <span className="text-muted library-sub">
                {video.channel ? `${video.channel} · ` : ''}added {formatRelative(video.created_at)}
              </span>
              {video.status === 'failed' && video.error_message && (
                <span role="alert" className="library-note library-note-error">
                  {video.error_message}
                </span>
              )}
              {(video.status === 'pending' || video.status === 'processing') && (
                <span className="text-muted library-note">
                  Processing — this can take a few minutes for long videos.
                </span>
              )}
            </span>
          </Link>
          <span className="library-actions">
            <span className={`tag ${TAG_CLASS[video.status]} library-tag`}>{video.status}</span>
            <button
              type="button"
              className="btn btn-ghost library-delete"
              onClick={() => handleDelete(video)}
              disabled={deleteVideo.isPending}
            >
              Delete
            </button>
          </span>
          {deleteVideo.isError && deleteVideo.variables === video.id && (
            <p role="alert" className="library-note library-note-error library-row-error">
              {deleteVideo.error.message}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}
```

- [ ] **Step 4: Run them to verify they pass**

Run: `docker compose exec -T web npx vitest run src/components/VideoList.test.tsx`
Expected: PASS (7 tests: `it.each` counts twice).

- [ ] **Step 5: Rewrite `web/src/components/AddVideoForm.tsx`**

```tsx
import { useState } from 'react'
import { useCreateVideo } from '../hooks/useVideos'
import { useToast } from './Toast'

export function AddVideoForm() {
  const [url, setUrl] = useState('')
  const createVideo = useCreateVideo()
  const toast = useToast()

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    createVideo.mutate(url, {
      onSuccess: () => {
        setUrl('')
        toast('Video added — processing')
      },
    })
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="library-add">
        <input
          className="input library-add-input"
          type="url"
          placeholder="https://www.youtube.com/watch?v=…"
          aria-label="YouTube URL"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          required
        />
        <button type="submit" className="btn btn-primary blueprint library-add-button" disabled={createVideo.isPending}>
          <i className="corner tl" />
          <i className="corner tr" />
          <i className="corner bl" />
          <i className="corner br" />
          {createVideo.isPending ? 'Adding…' : 'Add video'}
        </button>
      </div>
      {createVideo.error && (
        <p role="alert" className="library-add-error">
          {createVideo.error.message}
        </p>
      )}
    </form>
  )
}
```

- [ ] **Step 6: Rewrite `web/src/pages/LibraryPage.tsx`**

```tsx
import { AddVideoForm } from '../components/AddVideoForm'
import { AppHeader } from '../components/AppHeader'
import { VideoList } from '../components/VideoList'
import { useVideosQuery } from '../hooks/useVideos'
import './LibraryPage.css'

function countLabel(n: number): string {
  return `${n} ${n === 1 ? 'video' : 'videos'}`
}

export function LibraryPage() {
  const { data: videos, isLoading, error } = useVideosQuery()
  const count = countLabel(videos?.length ?? 0)

  return (
    <>
      <AppHeader meta={videos ? count : ''} />
      <main className="library">
        <h1 className="library-heading">Library</h1>
        <p className="text-muted library-intro">
          Add a YouTube URL. Grasp fetches the transcript, splits it into topic segments, embeds the chunks,
          and then every answer, card and question can point back to a timestamp.
        </p>
        <AddVideoForm />
        <div className="library-list-header">
          <h6>{count}</h6>
          <h6 className="text-muted">Newest first</h6>
        </div>
        {isLoading && <p className="text-muted library-empty">Loading…</p>}
        {error && (
          <p role="alert" className="library-add-error">
            {error.message}
          </p>
        )}
        {videos && <VideoList videos={videos} />}
      </main>
    </>
  )
}
```

- [ ] **Step 7: Add `web/src/pages/LibraryPage.css`**

```css
.library {
  max-width: 1020px;
  margin: 0 auto;
  padding: clamp(24px, 4vw, 44px) clamp(14px, 3vw, 28px) 80px;
}

.library-heading {
  margin: 0 0 var(--space-2);
}

.library-intro {
  max-width: 58ch;
  font-size: 15px;
  text-wrap: pretty;
}

.library-add {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin: var(--space-6) 0 var(--space-2);
}

.library-add-input {
  flex: 1 1 320px;
  min-width: 0;
}

.library-add-button {
  flex: 0 0 auto;
  padding-inline: var(--space-6);
}

.library-add-error,
.library-note-error {
  color: var(--color-accent-800);
}

.library-add-error {
  margin: 0 0 var(--space-2);
  font-size: 13px;
}

.library-list-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  margin-top: var(--space-6);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--color-divider);
}

.library-list-header h6 {
  margin: 0;
}

.library-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.library-empty {
  margin-top: var(--space-4);
}

.library-row {
  display: flex;
  gap: var(--space-4);
  flex-wrap: wrap;
  align-items: center;
  padding: var(--space-4) var(--space-2);
  border-bottom: 1px solid color-mix(in srgb, var(--color-text) 8%, transparent);
}

.library-row:hover {
  background: color-mix(in srgb, var(--color-text) 4%, transparent);
}

.library-row-link {
  flex: 1 1 400px;
  min-width: 0;
  display: flex;
  gap: var(--space-4);
  align-items: center;
  color: inherit;
  text-decoration: none;
}

.library-thumb {
  position: relative;
  flex: 0 0 auto;
  width: 124px;
  height: 70px;
  border: 1px solid var(--color-divider);
  background: repeating-linear-gradient(
    135deg,
    color-mix(in srgb, var(--color-text) 6%, transparent) 0 8px,
    transparent 8px 16px
  );
}

.library-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.library-duration {
  position: absolute;
  right: 4px;
  bottom: 4px;
  font-size: 11px;
  background: var(--color-bg);
  padding: 0 4px;
  border: 1px solid var(--color-divider);
}

.library-text {
  flex: 1 1 280px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.library-title {
  font-family: var(--font-heading);
  font-weight: 600;
  font-size: 19px;
  line-height: 1.18;
  text-wrap: pretty;
}

.library-sub {
  font-size: 13px;
}

.library-note {
  font-size: 12.5px;
  line-height: 1.45;
  text-wrap: pretty;
}

.library-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.library-tag {
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.library-delete {
  font-family: var(--font-body);
  font-size: 12.5px;
}

.library-row-error {
  flex-basis: 100%;
  margin: 0;
}
```

- [ ] **Step 8: Add the header to `web/src/pages/VideoDetailPage.tsx`**

Add `import { AppHeader } from '../components/AppHeader'`. Wrap the returned `<main>` in a fragment, with the header first:

```tsx
  return (
    <>
      <AppHeader meta={video?.youtube_id ?? ''} />
      <main>
        {/* existing contents unchanged */}
      </main>
    </>
  )
```

Re-indent the existing `<main>` block by one level. Don't change it otherwise. Sub-project 2 restyles it.

- [ ] **Step 9: Run every check**

Run: `docker compose exec -T web sh -c "npm test && npm run typecheck && npm run lint && npm run build"`
Expected: all pass.

- [ ] **Step 10: Manual check in the browser** (`docker compose restart web`, then open http://localhost:5173)

Compare against the prototype, `~/Downloads/design_handoff_grasp_ui/design/Grasp - Study Companion.dc.html`, in both themes:
- [ ] The header is sticky; GRASP links home; the meta reads "{n} videos"; the toggle switches the icon and theme.
- [ ] Reloading in dark mode shows no light flash. Toggling back to light and reloading stays light.
- [ ] The library heading, intro, add row (with corner marks on the button) and list header match.
- [ ] Rows show thumbnails and the duration badge (the podcast shows `3:02:45`), the channel line with relative time, tags in the right style, the 4% row hover, and Delete as a ghost button.
- [ ] Adding a duplicate URL shows "This video is already in the library." inline. Adding a new one shows the toast, and the row's tag updates live from pending to ready.
- [ ] The focus ring is the accent outline (keyboard Tab through the header and add row). There's no default blue ring.
- [ ] The video page shows the new header with the `youtube_id`, and still works: player, chat, decks and quizzes.

- [ ] **Step 11: Show the user, wait for approval, commit**

```bash
git add web/src/pages/LibraryPage.tsx web/src/pages/LibraryPage.css web/src/components/AddVideoForm.tsx web/src/components/VideoList.tsx web/src/components/VideoList.test.tsx web/src/pages/VideoDetailPage.tsx
git commit -m "feat: restyle the library with the Industry design system

Thumbnail with duration, channel and relative time, status tags, a
generic processing note, and toasts on add and delete. The video page
gets the new header; its layout changes in the next sub-project.

Refs #24"
```

---

## After the last task

Run the `code-reviewer` agent on the branch diff against `main` (`CLAUDE_WORKFLOW.md`'s gate). Open a PR only on a clean verdict and an explicit request from the user. The PR body says `Refs #24`, not `Closes`: four sub-projects remain.
