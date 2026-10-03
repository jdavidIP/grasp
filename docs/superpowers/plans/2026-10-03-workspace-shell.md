# Workspace Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the video page into the handoff's two-column workspace: player, title and topics on the left; a tabbed Chat / Flashcards / Quizzes panel that keeps each tab's state on the right. Make every seek fire, even to the same time twice. Sub-project 2 of 5 for #24.

**Architecture:**
- **Seeking:** the page owns a `SeekRequest` (`{ seconds, id }`) and one `seek(seconds)` callback that every timestamp feeds. The player reacts to each new request object.
- **Tabs:** `WorkspaceTabs` renders all three panels and hides the inactive ones, with the active tab synced to `?tab=`.
- **Contents:** today's chat, flashcard and quiz sections move into the panels as they are.

**Tech Stack:** React 19, TypeScript (strict), react-router 8 (`useSearchParams`), TanStack Query 5, Vitest 5 + React Testing Library + jsdom (Node 24 container).

**Spec:** `docs/superpowers/specs/2026-10-03-workspace-shell-design.md`

## Global Constraints

- **Branch:** `feat/24-workspace-shell`. One commit per task. **Before each commit, show the change and wait for the user's go-ahead** (`CLAUDE_WORKFLOW.md`). No `Co-Authored-By` trailer. Conventional messages ending with `Refs #24`.
- **Running commands:** all web commands run in the container: `docker compose exec -T web <cmd>`.
- **No new dependencies.** Values come from Industry tokens (`var(--…)`). App classes are prefixed `.workspace-*` (page) or `.youtube-player` (player).
- **Component files export only components** (oxlint `react(only-export-components)`). Shared helpers go in `web/src/lib/`. Types may be exported from component files.
- **Tests:** import from `'vitest'` explicitly. TypeScript strict, no `any`.
- **Fixed copy:**
  - Not-ready notes:
    - `pending`/`processing`: "Chat, flashcards and quizzes open once the video is processed."
    - `failed`: "This video couldn't be processed. Reprocess it to use chat, flashcards and quizzes."
  - Toast: "Jumped to {formatTime(seconds)}".
  - Empty topics: "No topics yet."
  - Tablist label: "Study tools".
- **Tab values:** `chat` | `flashcards` | `quizzes`. The URL param is `tab`, written with `replace: true`, and other params are kept.

## Review Focus

1. **The same timestamp clicked twice** (re-clicking a topic after watching on). The player seeks both times. Tested in Task 1.
2. **Typing in one tab, then switching away and back.** The text is still there. Tested in Task 2.
3. **A bad or stale `?tab=` value** (e.g. from an old link). The page opens on Chat instead of showing no panel. Tested in Task 2.
4. **A video with no channel, no duration, or exactly one segment.** The title line reads cleanly ("1 segment"), with no "null" and no dangling " · ". Tested in Task 4.
5. **A video still processing or failed.** No tabs. A plain note explains when chat, flashcards and quizzes will be available, and Reprocess shows only when it can run. Tested in Task 4.

---

## File Structure

| File | Responsibility |
|---|---|
| `web/src/components/YouTubePlayer.tsx` + `.css` | Seeks on every `SeekRequest`; the embed fills its container. Exports type `SeekRequest`. |
| `web/src/lib/format.ts` | `plural(n, word)`, `STATUS_TAG`. |
| `web/src/components/WorkspaceTabs.tsx` + `.css` | Tablist and three always-mounted panels, keyboard, `?tab=` sync. |
| `web/src/components/TopicList.tsx` | Topics header and seek rows (styles in `VideoDetailPage.css`). |
| `web/src/pages/VideoDetailPage.tsx` + `.css` | The shell: title row, player frame, topics, tabs or not-ready note, `seek` and toast. |
| `web/src/pages/LibraryPage.tsx`, `web/src/components/VideoList.tsx` | Switch to the shared `plural` / `STATUS_TAG` (no behaviour change). |

---

### Task 1: Seek on every request, and a player that fills its frame

**Files:**
- Modify: `web/src/components/YouTubePlayer.tsx`
- Create: `web/src/components/YouTubePlayer.css`
- Modify: `web/src/components/YouTubePlayer.test.tsx`
- Modify: `web/src/pages/VideoDetailPage.tsx` (seek state only)

**Interfaces:**
- Produces:
  - `export interface SeekRequest { seconds: number; id: number }`
  - `YouTubePlayer({ videoId, seek }: { videoId: string; seek: SeekRequest | null })`
  - In `VideoDetailPage`: `seek(seconds: number): void`, replacing `setSeekSeconds` in every `onSeek` prop.

- [ ] **Step 1: Update the existing test and add the failing one** (`web/src/components/YouTubePlayer.test.tsx`)

Make three changes:
- Change the existing test's two `<YouTubePlayer videoId="abc" seekSeconds={null} />` usages to `seek={null}`.
- Replace the module-cache comment above `afterEach` with:

```tsx
// YouTubePlayer caches its API-loading promise at module level. Each test sets window.YT
// before rendering, and the cached promise only reads window.YT when it resolves, so
// tests in this file can share it.
```

- Append:

```tsx
it('seeks every time it is asked, even to the same time twice', async () => {
  const seekTo = vi.fn()
  const playVideo = vi.fn()
  const Player = vi.fn(function () {
    return { seekTo, playVideo, destroy: vi.fn() }
  })
  window.YT = { Player } as unknown as NonNullable<Window['YT']>

  const { rerender } = render(<YouTubePlayer videoId="abc" seek={null} />)
  await waitFor(() => expect(Player).toHaveBeenCalled())

  rerender(<YouTubePlayer videoId="abc" seek={{ seconds: 30, id: 1 }} />)
  rerender(<YouTubePlayer videoId="abc" seek={{ seconds: 30, id: 2 }} />)

  expect(seekTo).toHaveBeenCalledTimes(2)
  expect(seekTo).toHaveBeenLastCalledWith(30, true)
  expect(playVideo).toHaveBeenCalledTimes(2)
})
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec -T web npx vitest run src/components/YouTubePlayer.test.tsx`
Expected: FAIL. The new test fails because `seek` isn't a prop yet: nothing seeks, so `seekTo` is called 0 times. The #25 test still passes.

- [ ] **Step 3: Implement `YouTubePlayer.tsx`**

Make these changes:
- Widen the options type in `YouTubeIframeApi`:

```tsx
    options: {
      videoId: string
      width?: string
      height?: string
      playerVars?: Record<string, number>
    },
```

- Replace the props interface and the component signature:

```tsx
// A new object per click, so seeking to the same time twice still seeks.
export interface SeekRequest {
  seconds: number
  id: number
}

interface YouTubePlayerProps {
  videoId: string
  // null means "nothing sought yet", distinct from a real 0:00 timestamp.
  seek: SeekRequest | null
}

export function YouTubePlayer({ videoId, seek }: YouTubePlayerProps) {
```

- In the player constructor call, use `{ videoId, width: '100%', height: '100%', playerVars: { autoplay: 1 } }`.
- Replace the seek effect with:

```tsx
  useEffect(() => {
    if (seek === null) return
    playerRef.current?.seekTo(seek.seconds, true)
    playerRef.current?.playVideo()
  }, [seek])
```

- Change the return to `return <div ref={wrapperRef} className="youtube-player" />`, and add `import './YouTubePlayer.css'` under the React import.

Create `web/src/components/YouTubePlayer.css`:

```css
/* Fills whatever frame the page gives it; the IFrame API's target and the iframe it
   swaps in are sized 100% by the player options. */
.youtube-player {
  width: 100%;
  height: 100%;
}
```

- [ ] **Step 4: Switch `VideoDetailPage.tsx` to seek requests**

Make these changes:
- Change `import { useState } from 'react'` to `import { useCallback, useState } from 'react'`.
- Change the `YouTubePlayer` import to `import { YouTubePlayer, type SeekRequest } from '../components/YouTubePlayer'`.
- Replace `const [seekSeconds, setSeekSeconds] = useState<number | null>(null)` with:

```tsx
  const [seekRequest, setSeekRequest] = useState<SeekRequest | null>(null)
  const seek = useCallback((seconds: number) => {
    setSeekRequest((previous) => ({ seconds, id: (previous?.id ?? 0) + 1 }))
  }, [])
```

- Replace every `onSeek={setSeekSeconds}` with `onSeek={seek}`.
- Replace `seekSeconds={seekSeconds}` with `seek={seekRequest}`.

- [ ] **Step 5: Run the tests and checks**

Run: `docker compose exec -T web sh -c "npx vitest run src/components/YouTubePlayer.test.tsx && npm test && npm run typecheck && npm run lint"`
Expected: both player tests pass. The full suite passes (26 tests). Typecheck exits 0, and lint reports 0 warnings.

- [ ] **Step 6: Show the user, wait for approval, commit**

```bash
git add web/src/components/YouTubePlayer.tsx web/src/components/YouTubePlayer.css web/src/components/YouTubePlayer.test.tsx web/src/pages/VideoDetailPage.tsx
git commit -m "fix: seek every time a timestamp is clicked

The player sought in an effect keyed on the seconds, so clicking the
same timestamp twice did nothing the second time. Each click is now a
new { seconds, id } request. The embed also fills its container instead
of YouTube's fixed default size.

Refs #24"
```

---

### Task 2: Tabbed panel that keeps each tab's state

**Files:**
- Create: `web/src/components/WorkspaceTabs.tsx`, `web/src/components/WorkspaceTabs.css`
- Test: `web/src/components/WorkspaceTabs.test.tsx`

**Interfaces:**
- Produces:
  - `export type TabId = 'chat' | 'flashcards' | 'quizzes'`
  - `WorkspaceTabs({ chat, flashcards, quizzes }: { chat: ReactNode; flashcards: ReactNode; quizzes: ReactNode })`. It must render inside a router.

- [ ] **Step 1: Write the failing tests** (`web/src/components/WorkspaceTabs.test.tsx`)

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation, useNavigationType } from 'react-router'
import { expect, it } from 'vitest'

import { WorkspaceTabs } from './WorkspaceTabs'

function LocationProbe() {
  const location = useLocation()
  const navigationType = useNavigationType()
  return <output data-testid="location">{`${navigationType} ${location.search}`}</output>
}

function renderTabs(entry = '/videos/v1') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <WorkspaceTabs
        chat={<input aria-label="Chat draft" />}
        flashcards={<p>Deck list</p>}
        quizzes={<p>Quiz list</p>}
      />
      <LocationProbe />
    </MemoryRouter>,
  )
}

function selectedTab() {
  return screen.getAllByRole('tab').find((tab) => tab.getAttribute('aria-selected') === 'true')
}

it('starts on Chat with linked tab and panel semantics', () => {
  renderTabs()
  expect(screen.getByRole('tablist', { name: 'Study tools' })).toBeTruthy()
  const tabs = screen.getAllByRole('tab')
  expect(tabs.map((tab) => tab.textContent)).toEqual(['Chat', 'Flashcards', 'Quizzes'])
  expect(selectedTab()?.textContent).toBe('Chat')
  expect(tabs.map((tab) => tab.tabIndex)).toEqual([0, -1, -1])

  const panel = screen.getByRole('tabpanel')
  expect(panel.id).toBe(tabs[0].getAttribute('aria-controls'))
  expect(panel.getAttribute('aria-labelledby')).toBe(tabs[0].id)
  const hiddenDecks = screen.getByText('Deck list').closest('[role="tabpanel"]') as HTMLElement
  expect(hiddenDecks.hidden).toBe(true)
})

it('moves selection and focus with the arrow keys, Home and End', () => {
  renderTabs()
  const tablist = screen.getByRole('tablist')

  fireEvent.keyDown(tablist, { key: 'ArrowLeft' })
  expect(selectedTab()?.textContent).toBe('Quizzes')
  expect(document.activeElement).toBe(selectedTab())

  fireEvent.keyDown(tablist, { key: 'ArrowRight' })
  expect(selectedTab()?.textContent).toBe('Chat')

  fireEvent.keyDown(tablist, { key: 'End' })
  expect(selectedTab()?.textContent).toBe('Quizzes')

  fireEvent.keyDown(tablist, { key: 'Home' })
  expect(selectedTab()?.textContent).toBe('Chat')
  expect(document.activeElement).toBe(selectedTab())
})

it('keeps a hidden panel mounted so what you typed survives switching', () => {
  renderTabs()
  fireEvent.change(screen.getByLabelText('Chat draft'), { target: { value: 'What is a loop?' } })

  fireEvent.click(screen.getByRole('tab', { name: 'Flashcards' }))
  expect(screen.getByRole('tabpanel').textContent).toBe('Deck list')
  fireEvent.click(screen.getByRole('tab', { name: 'Chat' }))

  expect(screen.getByLabelText('Chat draft')).toHaveProperty('value', 'What is a loop?')
})

it('opens the tab named in ?tab= and falls back to Chat for an unknown one', () => {
  const { unmount } = renderTabs('/videos/v1?tab=quizzes')
  expect(selectedTab()?.textContent).toBe('Quizzes')
  unmount()

  renderTabs('/videos/v1?tab=nonsense')
  expect(selectedTab()?.textContent).toBe('Chat')
})

it('writes the tab to the URL, replacing history and keeping other params', () => {
  renderTabs('/videos/v1?ref=library')
  fireEvent.click(screen.getByRole('tab', { name: 'Quizzes' }))
  expect(screen.getByTestId('location').textContent).toBe('REPLACE ?ref=library&tab=quizzes')
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `docker compose exec -T web npx vitest run src/components/WorkspaceTabs.test.tsx`
Expected: FAIL, because `./WorkspaceTabs` can't be resolved.

- [ ] **Step 3: Implement `web/src/components/WorkspaceTabs.tsx`**

```tsx
import { useRef, type KeyboardEvent, type ReactNode } from 'react'
import { useSearchParams } from 'react-router'
import './WorkspaceTabs.css'

export type TabId = 'chat' | 'flashcards' | 'quizzes'

const TABS: { id: TabId; label: string }[] = [
  { id: 'chat', label: 'Chat' },
  { id: 'flashcards', label: 'Flashcards' },
  { id: 'quizzes', label: 'Quizzes' },
]

function isTabId(value: string | null): value is TabId {
  return TABS.some((tab) => tab.id === value)
}

interface WorkspaceTabsProps {
  chat: ReactNode
  flashcards: ReactNode
  quizzes: ReactNode
}

export function WorkspaceTabs({ chat, flashcards, quizzes }: WorkspaceTabsProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const requested = searchParams.get('tab')
  const active: TabId = isTabId(requested) ? requested : 'chat'
  const tabRefs = useRef<Partial<Record<TabId, HTMLButtonElement | null>>>({})
  const panels: Record<TabId, ReactNode> = { chat, flashcards, quizzes }

  function select(id: TabId, moveFocus: boolean) {
    // replace: switching tabs shouldn't fill the Back button's history.
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous)
        next.set('tab', id)
        return next
      },
      { replace: true },
    )
    if (moveFocus) tabRefs.current[id]?.focus()
  }

  function handleKeyDown(event: KeyboardEvent) {
    const index = TABS.findIndex((tab) => tab.id === active)
    const targets: Record<string, number> = {
      ArrowRight: (index + 1) % TABS.length,
      ArrowLeft: (index - 1 + TABS.length) % TABS.length,
      Home: 0,
      End: TABS.length - 1,
    }
    if (!(event.key in targets)) return
    event.preventDefault()
    select(TABS[targets[event.key]].id, true)
  }

  return (
    <div className="blueprint workspace-tabs">
      <i className="corner tl" />
      <i className="corner tr" />
      <i className="corner bl" />
      <i className="corner br" />
      <div role="tablist" aria-label="Study tools" className="workspace-tablist" onKeyDown={handleKeyDown}>
        {TABS.map((tab) => (
          <button
            key={tab.id}
            ref={(element) => {
              tabRefs.current[tab.id] = element
            }}
            id={`workspace-tab-${tab.id}`}
            type="button"
            role="tab"
            aria-selected={active === tab.id}
            aria-controls={`workspace-panel-${tab.id}`}
            tabIndex={active === tab.id ? 0 : -1}
            className="workspace-tab"
            onClick={() => select(tab.id, false)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {/* All panels stay mounted (hidden when inactive) so a half-taken quiz or a typed
          question survives switching tabs. */}
      {TABS.map((tab) => (
        <div
          key={tab.id}
          id={`workspace-panel-${tab.id}`}
          role="tabpanel"
          aria-labelledby={`workspace-tab-${tab.id}`}
          hidden={active !== tab.id}
          className="workspace-panel"
        >
          {panels[tab.id]}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Add `web/src/components/WorkspaceTabs.css`**

```css
.workspace-tabs {
  display: flex;
  flex-direction: column;
  height: min(80vh, 840px);
  background: var(--color-bg);
}

.workspace-tablist {
  display: flex;
  border-bottom: 1px solid var(--color-divider);
}

.workspace-tab {
  flex: 1;
  padding: var(--space-3);
  border: none;
  border-right: 1px solid var(--color-divider);
  background: transparent;
  color: var(--color-text);
  cursor: pointer;
  font-family: var(--font-heading);
  font-weight: 600;
  font-size: 15px;
  letter-spacing: 0.02em;
}

.workspace-tab:last-child {
  border-right: none;
}

.workspace-tab[aria-selected='true'] {
  background: var(--color-accent);
  color: var(--color-bg);
}

.workspace-panel {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-6);
}

.workspace-panel[hidden] {
  display: none;
}
```

- [ ] **Step 5: Run the tests and checks**

Run: `docker compose exec -T web sh -c "npx vitest run src/components/WorkspaceTabs.test.tsx && npm run typecheck && npm run lint"`
Expected: PASS (5 tests). Typecheck exits 0, and lint reports 0 warnings.

- [ ] **Step 6: Show the user, wait for approval, commit**

```bash
git add web/src/components/WorkspaceTabs.tsx web/src/components/WorkspaceTabs.css web/src/components/WorkspaceTabs.test.tsx
git commit -m "feat: add a tabbed panel that keeps each tab's state

Chat, Flashcards and Quizzes as a real tablist with arrow/Home/End
keys. Inactive panels stay mounted but hidden, so switching keeps what
you were doing, and the active tab is kept in ?tab= without adding
history entries.

Refs #24"
```

---

### Task 3: Shared format helpers and the topics list

**Files:**
- Create: `web/src/lib/format.ts`, `web/src/lib/format.test.ts`
- Create: `web/src/components/TopicList.tsx`, `web/src/components/TopicList.test.tsx`
- Modify: `web/src/pages/LibraryPage.tsx`, `web/src/components/VideoList.tsx` (use the shared helpers)

**Interfaces:**
- Produces:
  - `plural(n: number, word: string): string`. Returns `"1 segment"` or `"2 segments"` (it appends `s`).
  - `STATUS_TAG: Record<VideoStatus, string>`
  - `TopicList({ segments, onSeek }: { segments: Segment[]; onSeek: (seconds: number) => void })`
- Consumes: `formatTime` (`lib/time.ts`), `Segment` and `VideoStatus` (`types/video.ts`).

- [ ] **Step 1: Write the failing tests**

`web/src/lib/format.test.ts`:

```ts
import { expect, it } from 'vitest'

import { STATUS_TAG, plural } from './format'

it('pluralises a count', () => {
  expect(plural(0, 'segment')).toBe('0 segments')
  expect(plural(1, 'segment')).toBe('1 segment')
  expect(plural(7, 'video')).toBe('7 videos')
})

it('maps every status to its tag class', () => {
  expect(STATUS_TAG).toEqual({
    ready: 'tag-accent',
    failed: 'tag-outline',
    pending: 'tag-neutral',
    processing: 'tag-neutral',
  })
})
```

`web/src/components/TopicList.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'

import type { Segment } from '../types/video'
import { TopicList } from './TopicList'

const segment: Segment = {
  id: 's1',
  label: 'Loops',
  summary: 'For and while loops.',
  start_time: 298,
  end_time: 547,
}

it('seeks to a topic’s start when it is clicked', () => {
  const onSeek = vi.fn()
  render(<TopicList segments={[segment]} onSeek={onSeek} />)
  expect(screen.getByText('1 segment')).toBeTruthy()

  fireEvent.click(screen.getByRole('button', { name: /Loops/ }))
  expect(onSeek).toHaveBeenCalledWith(298)
  expect(screen.getByRole('button', { name: /Loops/ }).textContent).toContain('4:58–9:07')
})

it('says so when there are no topics yet', () => {
  render(<TopicList segments={[]} onSeek={vi.fn()} />)
  expect(screen.getByText('No topics yet.')).toBeTruthy()
  expect(screen.getByText('0 segments')).toBeTruthy()
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `docker compose exec -T web npx vitest run src/lib/format.test.ts src/components/TopicList.test.tsx`
Expected: FAIL, because `./format` and `./TopicList` can't be resolved.

- [ ] **Step 3: Implement `web/src/lib/format.ts`**

```ts
import type { VideoStatus } from '../types/video'

export function plural(n: number, word: string): string {
  return `${n} ${n === 1 ? word : `${word}s`}`
}

export const STATUS_TAG: Record<VideoStatus, string> = {
  ready: 'tag-accent',
  failed: 'tag-outline',
  pending: 'tag-neutral',
  processing: 'tag-neutral',
}
```

- [ ] **Step 4: Implement `web/src/components/TopicList.tsx`**

```tsx
import { plural } from '../lib/format'
import { formatTime } from '../lib/time'
import type { Segment } from '../types/video'

interface TopicListProps {
  segments: Segment[]
  onSeek: (seconds: number) => void
}

export function TopicList({ segments, onSeek }: TopicListProps) {
  return (
    <section className="workspace-topics" aria-label="Topics">
      <div className="workspace-section-header">
        <h6>Topics</h6>
        <h6 className="text-muted">{plural(segments.length, 'segment')}</h6>
      </div>
      {segments.length === 0 ? (
        <p className="text-muted workspace-empty">No topics yet.</p>
      ) : (
        <ul className="workspace-topic-list">
          {segments.map((segment) => (
            <li key={segment.id}>
              <button type="button" className="workspace-topic" onClick={() => onSeek(segment.start_time)}>
                <span className="workspace-topic-range tabular">
                  {formatTime(segment.start_time)}–{formatTime(segment.end_time)}
                </span>
                <span className="workspace-topic-text">
                  <span className="workspace-topic-label">{segment.label}</span>
                  <span className="text-muted workspace-topic-summary">{segment.summary}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
```

- [ ] **Step 5: Use the shared helpers in the Library**

Make these changes:
- In `web/src/pages/LibraryPage.tsx`:
  - Delete the `countLabel` function.
  - Add `import { plural } from '../lib/format'`.
  - Change `const count = countLabel(videos?.length ?? 0)` to `const count = plural(videos?.length ?? 0, 'video')`.
- In `web/src/components/VideoList.tsx`:
  - Delete the `TAG_CLASS` constant.
  - Add `import { STATUS_TAG } from '../lib/format'`.
  - Change `TAG_CLASS[video.status]` to `STATUS_TAG[video.status]`.

- [ ] **Step 6: Run the tests and checks**

Run: `docker compose exec -T web sh -c "npx vitest run src/lib/format.test.ts src/components/TopicList.test.tsx && npm test && npm run typecheck && npm run lint"`
Expected: the new tests pass (4). The full suite passes, including the existing Library tests, unchanged. Typecheck exits 0, and lint reports 0 warnings.

- [ ] **Step 7: Show the user, wait for approval, commit**

```bash
git add web/src/lib/format.ts web/src/lib/format.test.ts web/src/components/TopicList.tsx web/src/components/TopicList.test.tsx web/src/pages/LibraryPage.tsx web/src/components/VideoList.tsx
git commit -m "feat: add a topics list that seeks the player

Each topic is a button that seeks to its start. plural() and the status
tag map move to lib/format.ts so the Library and the workspace share
them.

Refs #24"
```

---

### Task 4: The workspace page

**Files:**
- Modify (rewrite): `web/src/pages/VideoDetailPage.tsx`
- Create: `web/src/pages/VideoDetailPage.css`
- Test: `web/src/pages/VideoDetailPage.test.tsx`

**Interfaces:**
- Consumes:
  - `YouTubePlayer`, `SeekRequest` (Task 1)
  - `WorkspaceTabs` (Task 2)
  - `TopicList`, `plural`, `STATUS_TAG` (Task 3)
  - `AppHeader`, `useToast` (`lib/toast`), `formatTime`
  - existing hooks: `useVideoQuery`, `useReprocessVideo`
  - existing components: `ChatPanel`, `FlashcardConfigModal`, `FlashcardDeckList`, `FlashcardReview`, `QuizConfigModal`, `QuizList`, `QuizTake`, `QuizAttemptHistory`, all with unchanged props.
- Produces: `VideoDetailPage()`, routed at `/videos/:id`.

- [ ] **Step 1: Write the failing tests** (`web/src/pages/VideoDetailPage.test.tsx`)

```tsx
import { fireEvent, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, expect, it, vi } from 'vitest'

import { ToastProvider } from '../components/Toast'
import { jsonResponse, renderWithClient } from '../test/render'
import type { VideoDetail } from '../types/video'
import { VideoDetailPage } from './VideoDetailPage'

afterEach(() => {
  vi.unstubAllGlobals()
  delete window.YT
})

function video(overrides: Partial<VideoDetail>): VideoDetail {
  return {
    id: 'v1',
    youtube_id: 'abc123',
    title: 'A lecture',
    channel: 'YaleCourses',
    duration_seconds: 3375,
    thumbnail_url: null,
    status: 'ready',
    error_message: null,
    created_at: '2026-10-01T12:00:00Z',
    transcript_source: 'youtube',
    segments: [
      { id: 's1', label: 'Intro', summary: 'Opening.', start_time: 8, end_time: 148 },
      { id: 's2', label: 'Berlin', summary: 'The wall.', start_time: 232, end_time: 365 },
    ],
    ...overrides,
  }
}

function renderPage(detail: VideoDetail) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      url.endsWith('/videos/v1') ? jsonResponse(200, detail) : jsonResponse(200, []),
    ),
  )
  return renderWithClient(
    <ToastProvider>
      <MemoryRouter initialEntries={['/videos/v1']}>
        <Routes>
          <Route path="/videos/:id" element={<VideoDetailPage />} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>,
  )
}

it('shows channel, duration and segment count under the title', async () => {
  renderPage(video({}))
  expect(await screen.findByText('YaleCourses · 56:15 · 2 segments')).toBeTruthy()
  expect(screen.getByRole('heading', { name: 'A lecture' })).toBeTruthy()
})

it('leaves out a missing channel and duration and says "1 segment"', async () => {
  renderPage(
    video({
      channel: null,
      duration_seconds: null,
      segments: [{ id: 's1', label: 'Only', summary: 'One.', start_time: 0, end_time: 60 }],
    }),
  )
  expect(await screen.findByText('1 segment', { selector: '.workspace-meta' })).toBeTruthy()
  expect(document.body.textContent).not.toContain('null')
})

it('shows the tabs for a ready video and toasts each seek', async () => {
  renderPage(video({}))
  expect(await screen.findByRole('tablist', { name: 'Study tools' })).toBeTruthy()

  fireEvent.click(screen.getByRole('button', { name: /Berlin/ }))
  expect(screen.getByRole('status').textContent).toBe('Jumped to 3:52')
})

it('explains the wait instead of showing tabs while processing', async () => {
  renderPage(video({ status: 'processing', segments: [] }))
  expect(
    await screen.findByText('Chat, flashcards and quizzes open once the video is processed.'),
  ).toBeTruthy()
  expect(screen.queryByRole('tablist')).toBeNull()
  expect(screen.queryByRole('button', { name: 'Reprocess' })).toBeNull()
})

it('shows the failure, the error and Reprocess for a failed video', async () => {
  renderPage(video({ status: 'failed', error_message: 'No transcript available.', segments: [] }))
  expect(
    await screen.findByText(
      "This video couldn't be processed. Reprocess it to use chat, flashcards and quizzes.",
    ),
  ).toBeTruthy()
  expect(screen.getByRole('alert').textContent).toBe('No transcript available.')
  expect(screen.getByRole('button', { name: 'Reprocess' })).toBeTruthy()
  expect(screen.queryByRole('tablist')).toBeNull()
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `docker compose exec -T web npx vitest run src/pages/VideoDetailPage.test.tsx`
Expected: FAIL. The old page has no meta line, no tablist, no toast and no not-ready notes.

- [ ] **Step 3: Rewrite `web/src/pages/VideoDetailPage.tsx`**

```tsx
import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router'
import { AppHeader } from '../components/AppHeader'
import { ChatPanel } from '../components/ChatPanel'
import { FlashcardConfigModal } from '../components/FlashcardConfigModal'
import { FlashcardDeckList } from '../components/FlashcardDeckList'
import { FlashcardReview } from '../components/FlashcardReview'
import { QuizAttemptHistory } from '../components/QuizAttemptHistory'
import { QuizConfigModal } from '../components/QuizConfigModal'
import { QuizList } from '../components/QuizList'
import { QuizTake } from '../components/QuizTake'
import { TopicList } from '../components/TopicList'
import { WorkspaceTabs } from '../components/WorkspaceTabs'
import { YouTubePlayer, type SeekRequest } from '../components/YouTubePlayer'
import { useReprocessVideo, useVideoQuery } from '../hooks/useVideos'
import { STATUS_TAG, plural } from '../lib/format'
import { formatTime } from '../lib/time'
import { useToast } from '../lib/toast'
import './VideoDetailPage.css'

function Corners() {
  return (
    <>
      <i className="corner tl" />
      <i className="corner tr" />
      <i className="corner bl" />
      <i className="corner br" />
    </>
  )
}

export function VideoDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: video, isLoading, error } = useVideoQuery(id!)
  const reprocess = useReprocessVideo(id!)
  const toast = useToast()
  const [seekRequest, setSeekRequest] = useState<SeekRequest | null>(null)
  const [reviewingDeckId, setReviewingDeckId] = useState<string | null>(null)
  const [activeQuiz, setActiveQuiz] = useState<{ id: string; mode: 'take' | 'history' } | null>(
    null,
  )

  const seek = useCallback(
    (seconds: number) => {
      setSeekRequest((previous) => ({ seconds, id: (previous?.id ?? 0) + 1 }))
      toast(`Jumped to ${formatTime(seconds)}`)
    },
    [toast],
  )

  const inProgress = video?.status === 'pending' || video?.status === 'processing'
  const meta = video
    ? [
        video.channel,
        video.duration_seconds !== null ? formatTime(video.duration_seconds) : null,
        plural(video.segments.length, 'segment'),
      ]
        .filter(Boolean)
        .join(' · ')
    : ''

  return (
    <>
      <AppHeader meta={video?.youtube_id ?? ''} />
      <main className="workspace">
        <Link to="/" className="btn btn-secondary workspace-back">
          ← Library
        </Link>
        {isLoading && <p className="text-muted">Loading…</p>}
        {error && (
          <p role="alert" className="workspace-error">
            {error.message}
          </p>
        )}
        {video && (
          <div className="workspace-columns">
            <div className="workspace-left">
              <div className="workspace-title-row">
                <div className="workspace-title">
                  <h2>{video.title}</h2>
                  <span className="text-muted tabular workspace-meta">{meta}</span>
                </div>
                <div className="workspace-title-actions">
                  <span className={`tag ${STATUS_TAG[video.status]} workspace-tag`}>{video.status}</span>
                  {!inProgress && (
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => reprocess.mutate()}
                      disabled={reprocess.isPending}
                    >
                      Reprocess
                    </button>
                  )}
                </div>
              </div>
              {reprocess.isError && (
                <p role="alert" className="workspace-error">
                  {reprocess.error.message}
                </p>
              )}
              {video.status === 'failed' && video.error_message && (
                <p role="alert" className="workspace-error">
                  {video.error_message}
                </p>
              )}

              {video.status === 'ready' && (
                <figure className="blueprint workspace-player">
                  <Corners />
                  <YouTubePlayer videoId={video.youtube_id} seek={seekRequest} />
                </figure>
              )}

              <TopicList segments={video.segments} onSeek={seek} />
            </div>

            <div className="workspace-right">
              {video.status === 'ready' ? (
                <WorkspaceTabs
                  chat={<ChatPanel videoId={video.id} onSeek={seek} />}
                  flashcards={
                    <>
                      <FlashcardConfigModal
                        videoId={video.id}
                        segments={video.segments}
                        onCreated={setReviewingDeckId}
                      />
                      <FlashcardDeckList
                        videoId={video.id}
                        onReview={setReviewingDeckId}
                        onDeleted={(deckId) =>
                          setReviewingDeckId((current) => (current === deckId ? null : current))
                        }
                      />
                      {reviewingDeckId && (
                        <FlashcardReview
                          key={reviewingDeckId}
                          deckId={reviewingDeckId}
                          onSeek={seek}
                          onClose={() => setReviewingDeckId(null)}
                        />
                      )}
                    </>
                  }
                  quizzes={
                    <>
                      <QuizConfigModal
                        videoId={video.id}
                        segments={video.segments}
                        onCreated={(quizId) => setActiveQuiz({ id: quizId, mode: 'take' })}
                      />
                      <QuizList
                        videoId={video.id}
                        onTake={(quizId) => setActiveQuiz({ id: quizId, mode: 'take' })}
                        onHistory={(quizId) => setActiveQuiz({ id: quizId, mode: 'history' })}
                        onDeleted={(quizId) =>
                          setActiveQuiz((current) => (current?.id === quizId ? null : current))
                        }
                      />
                      {activeQuiz?.mode === 'take' && (
                        <QuizTake
                          key={activeQuiz.id}
                          videoId={video.id}
                          quizId={activeQuiz.id}
                          onSeek={seek}
                          onClose={() => setActiveQuiz(null)}
                        />
                      )}
                      {activeQuiz?.mode === 'history' && (
                        <QuizAttemptHistory
                          key={activeQuiz.id}
                          quizId={activeQuiz.id}
                          onSeek={seek}
                          onClose={() => setActiveQuiz(null)}
                        />
                      )}
                    </>
                  }
                />
              ) : (
                <div className="blueprint workspace-unavailable">
                  <Corners />
                  <p className="text-muted">
                    {video.status === 'failed'
                      ? "This video couldn't be processed. Reprocess it to use chat, flashcards and quizzes."
                      : 'Chat, flashcards and quizzes open once the video is processed.'}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </>
  )
}
```

- [ ] **Step 4: Add `web/src/pages/VideoDetailPage.css`**

```css
.workspace {
  max-width: 1460px;
  margin: 0 auto;
  padding: clamp(16px, 2.5vw, 26px) clamp(14px, 3vw, 28px) 56px;
}

.workspace-back {
  display: inline-flex;
  margin-bottom: var(--space-4);
  text-decoration: none;
}

.workspace-error {
  margin: 0;
  font-size: 13px;
  color: var(--color-accent-800);
}

.workspace-columns {
  display: flex;
  flex-wrap: wrap;
  gap: clamp(20px, 2.2vw, 30px);
  align-items: flex-start;
}

.workspace-left {
  flex: 1 1 520px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.workspace-right {
  flex: 1 1 430px;
  min-width: 0;
}

.workspace-title-row {
  display: flex;
  gap: var(--space-4);
  align-items: flex-start;
  flex-wrap: wrap;
}

.workspace-title {
  flex: 1 1 320px;
  min-width: 0;
}

.workspace-title h2 {
  margin: 0 0 var(--space-1);
  text-wrap: pretty;
}

.workspace-meta {
  font-size: 13px;
}

.workspace-title-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.workspace-tag {
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.workspace-player {
  aspect-ratio: 16 / 9;
}

.workspace-section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--color-divider);
}

.workspace-section-header h6 {
  margin: 0;
}

.workspace-empty {
  margin-top: var(--space-3);
}

.workspace-topic-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.workspace-topic {
  display: flex;
  gap: var(--space-4);
  align-items: baseline;
  width: 100%;
  padding: var(--space-3) var(--space-1);
  border: none;
  border-bottom: 1px solid color-mix(in srgb, var(--color-text) 8%, transparent);
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.workspace-topic:hover {
  background: color-mix(in srgb, var(--color-text) 4%, transparent);
}

.workspace-topic-range {
  flex: 0 0 auto;
  min-width: 92px;
  font-size: 12.5px;
  color: var(--color-accent-700);
}

.workspace-topic-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.workspace-topic-label {
  font-family: var(--font-heading);
  font-weight: 600;
  font-size: 16px;
  line-height: 1.2;
}

.workspace-topic-summary {
  font-size: 13px;
  line-height: 1.45;
  text-wrap: pretty;
}

.workspace-unavailable {
  display: flex;
  align-items: center;
  justify-content: center;
  height: min(80vh, 840px);
  padding: var(--space-6);
  text-align: center;
  background: var(--color-bg);
}

.workspace-unavailable p {
  margin: 0;
  max-width: 40ch;
}
```

- [ ] **Step 5: Run the tests and checks**

Run: `docker compose exec -T web sh -c "npx vitest run src/pages/VideoDetailPage.test.tsx && npm test && npm run typecheck && npm run lint && npm run build"`
Expected: the 5 page tests pass and the full suite passes. Typecheck exits 0, lint reports 0 warnings, and the build succeeds.

- [ ] **Step 6: Manual check in the browser** (`docker compose restart web`, then open a ready video at http://localhost:5173)

Compare against the prototype in both themes at 1280px wide, then at about 800px wide:
- [ ] Two columns at 1280px, stacked at 800px. Nothing overflows sideways.
- [ ] The title row shows the meta line, status tag and Reprocess. The player fills its 16:9 frame, with corner marks.
- [ ] Clicking a topic seeks the video and toasts "Jumped to …". Clicking the **same** topic again after the video has moved on seeks again.
- [ ] Tabs: clicking works, Tab focuses the active tab, and arrows, Home and End move between tabs. The active tab is filled with the accent.
- [ ] Type in chat, switch to Quizzes and back: the text is still there. Also check whether the chat panel's scroll position survives, and record what you see (the spec doesn't promise it).
- [ ] `?tab=quizzes` survives a reload. The Back button leaves the page rather than stepping back through tabs.
- [ ] Chat answers, flashcard and quiz creation, review, taking a quiz and viewing history all still work inside the tabs, including their seek buttons.
- [ ] A processing video (after Reprocess) shows the note in the right column and switches to tabs once it's ready.

- [ ] **Step 7: Show the user, wait for approval, commit**

```bash
git add web/src/pages/VideoDetailPage.tsx web/src/pages/VideoDetailPage.css web/src/pages/VideoDetailPage.test.tsx
git commit -m "feat: restructure the video page into a two-column workspace

Player, title and topics on the left; Chat, Flashcards and Quizzes in a
tabbed panel on the right, which explains the wait while the video
isn't ready. Every seek shows a toast. The tab contents move in as they
are; they get restyled in the next sub-projects.

Refs #24"
```

---

## After the last task

Run the `code-reviewer` agent on the branch diff against `main` (`CLAUDE_WORKFLOW.md`'s gate). Open a PR only on a clean verdict and an explicit request from the user. The PR body says `Refs #24`: three sub-projects remain.
