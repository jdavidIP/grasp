# Flashcards Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Flashcards tab becomes one panel (deck list → config → generating → review) in the Industry design, replacing the config modal, and shows each card's speaker-slip note. Sub-project 4 of 5 for #24.

**Architecture:** `FlashcardsPanel` owns the view and the config draft; the existing TanStack hooks are unchanged. "Generating" is not stored: it is the config view while the create mutation is pending, so a failure falls back to the form with its error and the draft intact. Frontend only.

**Tech Stack:** React 19, TypeScript strict, TanStack Query 5, Vitest 5 + React Testing Library + jsdom.

**Spec:** `docs/superpowers/specs/2026-10-03-flashcards-tab-design.md`

## Global Constraints

- **Branch:** `feat/24-flashcards-tab`. One commit per task. **Before each commit, show the change and wait for the user's go-ahead** (only "skip my review" waives it). No `Co-Authored-By` trailer. Conventional messages ending with `Refs #24`.
- **Commands** run in the container: `docker compose exec -T web <cmd>`. `docker compose restart web` before browser checks. **Never run tools the repo doesn't use** (no prettier); match the existing style: single quotes, no semicolons.
- **No new dependencies.** Industry tokens only (`var(--…)`); app classes prefixed `.fc-*`.
- **Component files export only components** (oxlint `only-export-components`); helpers go in `web/src/lib/`, types in `web/src/types/`.
- **Tests** import from `'vitest'` explicitly; no `any`.
- **Fixed copy:** "Flashcard decks", "New deck", "No flashcard decks yet.", "Loading…", "Review", "Delete", `Delete the deck "{title}"? This cannot be undone.`, "Cards", "Scope", "Whole video", "Selected topics", "Topics", "{n} of {total} selected", "No topics available.", "Difficulty", "Style", "Title (generated if blank)", "Generate {count} cards", "Select at least one topic", "Cancel", "Generating deck…", "Retrieving passages, drafting cards and checking each one against the transcript.", "{s}s elapsed", "Card {i} of {n}", "Click to reveal answer", "Hide answer", "Jump to {mm:ss}", "← Previous", "Next →", "Close", "This deck has no cards."

## Review Focus

1. **Shortcuts from another tab** — typing Space/arrows in the chat while a deck is open in the (hidden) Flashcards tab must not flip or move cards. Handled by scoping `onKeyDown` to the review section; tested in Task 3.
2. **Double submit while generating** — a second Generate must not create a second deck. The form unmounts the moment the mutation is pending; tested in Task 2.
3. **Arrow keys after clicking Next** — focus sits on the Next button; arrows must still move. Only Space/Enter defer to a focused control; tested in Task 3.
4. **A 422 from the generator** — back on the form with the server's message and the typed title kept; tested in Task 2.
5. **Long front/back text** — wraps inside the card (`overflow-wrap: anywhere`); checked in the browser (Task 4).

---

## File Structure

| File | Responsibility |
|---|---|
| `web/src/types/flashcard.ts` | `Flashcard.note`; `FlashcardDraft` |
| `web/src/lib/format.ts` (+ test) | `deckConfigSummary(config)` |
| `web/src/components/Corners.tsx` | the four blueprint corner marks (moved out of `VideoDetailPage`) |
| `web/src/components/FlashcardDeckList.tsx` (+ test) | deck cards, summary, delete |
| `web/src/components/FlashcardConfigForm.tsx` | controlled config form (replaces `FlashcardConfigModal.tsx`) |
| `web/src/components/FlashcardGenerating.tsx` | status + elapsed counter |
| `web/src/components/FlashcardsPanel.tsx` (+ test) | view, draft, flow |
| `web/src/components/FlashcardReview.tsx` (+ test) | card, strip, kicker, note, keyboard |
| `web/src/components/Flashcards.css` | `.fc-*` |
| `web/src/pages/VideoDetailPage.tsx` | Flashcards tab renders the panel |

---

### Task 1: Deck list, config summary, note type

**Files:** `web/src/types/flashcard.ts`, `web/src/lib/format.ts`, `web/src/lib/format.test.ts`, `web/src/components/Corners.tsx` (new), `web/src/components/FlashcardDeckList.tsx`, `web/src/components/FlashcardDeckList.test.tsx` (new), `web/src/components/Flashcards.css` (new), `web/src/pages/VideoDetailPage.tsx`

**Interfaces — produces:** `deckConfigSummary(config: Record<string, unknown>): string`; `Corners` component; `FlashcardDeckList({ videoId, onNew?, onReview })` (`onNew` optional until Task 2 wires it; `onDeleted` removed).

- [ ] **Step 1: Failing tests**

Append to `web/src/lib/format.test.ts` (and import `deckConfigSummary`):

```ts
it('summarises a deck config', () => {
  expect(deckConfigSummary({ scope: 'whole_video', difficulty: 'mixed', style: 'concept' })).toBe(
    'Whole video · mixed · concept',
  )
  expect(
    deckConfigSummary({ scope: 'topics', segment_ids: ['a', 'b', 'c'], difficulty: 'hard', style: 'detail' }),
  ).toBe('3 topics · hard · detail')
  expect(deckConfigSummary({ scope: 'topics', segment_ids: ['a'], difficulty: 'easy', style: 'mixed' })).toBe(
    '1 topic · easy · mixed',
  )
  // An older or partial config leaves parts out instead of printing "undefined".
  expect(deckConfigSummary({ scope: 'whole_video' })).toBe('Whole video')
  expect(deckConfigSummary({})).toBe('')
})
```

Create `web/src/components/FlashcardDeckList.test.tsx`:

```tsx
import { fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import type { FlashcardDeckListItem } from '../types/flashcard'
import { FlashcardDeckList } from './FlashcardDeckList'

afterEach(() => {
  vi.unstubAllGlobals()
})

const deck: FlashcardDeckListItem = {
  id: 'd1',
  video_id: 'v1',
  title: 'Loops',
  config: { scope: 'topics', segment_ids: ['s1', 's2'], difficulty: 'hard', style: 'detail' },
  created_at: new Date().toISOString(),
  card_count: 12,
}

function stubDecks(decks: FlashcardDeckListItem[]) {
  const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => jsonResponse(200, decks))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

it('shows each deck with its card count, date and config summary', async () => {
  stubDecks([deck])
  const onReview = vi.fn()
  renderWithClient(<FlashcardDeckList videoId="v1" onReview={onReview} />)

  expect(await screen.findByText('Loops')).toBeTruthy()
  expect(screen.getByText(/^12 cards · /)).toBeTruthy()
  expect(screen.getByText('2 topics · hard · detail')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Review' }))
  expect(onReview).toHaveBeenCalledWith('d1')
})

it('sends nothing when Delete is cancelled', async () => {
  const fetchMock = stubDecks([deck])
  vi.stubGlobal('confirm', vi.fn(() => false))
  renderWithClient(<FlashcardDeckList videoId="v1" onReview={() => {}} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))

  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
})

it('says when there are no decks yet', async () => {
  stubDecks([])
  renderWithClient(<FlashcardDeckList videoId="v1" onReview={() => {}} />)
  expect(await screen.findByText('No flashcard decks yet.')).toBeTruthy()
})
```

- [ ] **Step 2: Run, expect FAIL** — `docker compose exec -T web npm test -- format FlashcardDeckList`

- [ ] **Step 3: Implement**

`web/src/types/flashcard.ts`: `Flashcard` gains `note: string | null` (after `order_index`, mirroring `FlashcardOut`), and add:

```ts
// The config form's working state; `FlashcardsPanel` turns it into a FlashcardConfig.
export interface FlashcardDraft {
  count: number
  scope: FlashcardScope
  segmentIds: string[]
  difficulty: FlashcardDifficulty
  style: FlashcardStyle
  title: string
}
```

`web/src/lib/format.ts`:

```ts
// One line describing a deck's stored config, e.g. "3 topics · hard · detail". Parts
// missing from an older or partial config are left out.
export function deckConfigSummary(config: Record<string, unknown>): string {
  const { scope, segment_ids: segmentIds, difficulty, style } = config
  const scopePart =
    scope === 'whole_video'
      ? 'Whole video'
      : scope === 'topics' && Array.isArray(segmentIds)
        ? plural(segmentIds.length, 'topic')
        : null
  return [scopePart, difficulty, style]
    .filter((part): part is string => typeof part === 'string')
    .join(' · ')
}
```

`web/src/components/Corners.tsx` — move `Corners` out of `VideoDetailPage.tsx` unchanged (export it), and import it there instead of the local copy:

```tsx
// The four registration marks every `.blueprint` frame needs.
export function Corners() {
  return (
    <>
      <i className="corner tl" />
      <i className="corner tr" />
      <i className="corner bl" />
      <i className="corner br" />
    </>
  )
}
```

`web/src/components/FlashcardDeckList.tsx`:

```tsx
import { useDeleteFlashcardDeck, useFlashcardDecksQuery } from '../hooks/useFlashcards'
import { deckConfigSummary, plural } from '../lib/format'
import { formatRelative } from '../lib/time'
import { Corners } from './Corners'
import './Flashcards.css'

interface FlashcardDeckListProps {
  videoId: string
  onNew?: () => void
  onReview: (deckId: string) => void
}

export function FlashcardDeckList({ videoId, onNew, onReview }: FlashcardDeckListProps) {
  const { data: decks, isLoading, error } = useFlashcardDecksQuery(videoId)
  const deleteDeck = useDeleteFlashcardDeck(videoId)

  function handleDelete(deckId: string, title: string) {
    if (!window.confirm(`Delete the deck "${title}"? This cannot be undone.`)) return
    deleteDeck.mutate(deckId)
  }

  return (
    <section className="fc-list">
      <div className="fc-list-head">
        <h3>Flashcard decks</h3>
        {onNew && (
          <button type="button" className="btn btn-primary" onClick={onNew}>
            New deck
          </button>
        )}
      </div>
      {isLoading && <p className="text-muted">Loading…</p>}
      {error && (
        <p role="alert" className="fc-error">
          {error.message}
        </p>
      )}
      {decks?.length === 0 && <p className="text-muted">No flashcard decks yet.</p>}
      {decks?.map((deck) => (
        <article key={deck.id} className="blueprint fc-deck">
          <Corners />
          <div className="fc-deck-head">
            <span className="fc-deck-title">{deck.title}</span>
            <span className="text-muted tabular fc-deck-meta">
              {plural(deck.card_count, 'card')} · {formatRelative(deck.created_at)}
            </span>
          </div>
          <span className="text-muted fc-deck-summary">{deckConfigSummary(deck.config)}</span>
          <div className="fc-deck-actions">
            <button type="button" className="btn btn-secondary" onClick={() => onReview(deck.id)}>
              Review
            </button>
            <button
              type="button"
              className="btn btn-ghost fc-small"
              onClick={() => handleDelete(deck.id, deck.title)}
              disabled={deleteDeck.isPending}
            >
              Delete
            </button>
          </div>
          {deleteDeck.isError && deleteDeck.variables === deck.id && (
            <p role="alert" className="fc-error">
              {deleteDeck.error.message}
            </p>
          )}
        </article>
      ))}
    </section>
  )
}
```

`VideoDetailPage.tsx`: `FlashcardDeckList` loses `onDeleted` (the modal still provides "New deck" until Task 2):

```tsx
<FlashcardDeckList videoId={video.id} onReview={setReviewingDeckId} />
```

`web/src/components/Flashcards.css` (Task 1 part; later tasks append):

```css
.fc-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.fc-list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.fc-list-head h3 {
  margin: 0;
}

.fc-deck {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
}

.fc-deck-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.fc-deck-title {
  font-family: var(--font-heading);
  font-weight: 600;
  font-size: 18px;
  overflow-wrap: anywhere;
}

.fc-deck-meta {
  font-size: 12px;
}

.fc-deck-summary {
  font-size: 12.5px;
}

.fc-deck-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-1);
}

.fc-small {
  font-size: 12.5px;
}

.fc-error {
  margin: 0;
  font-size: 13px;
  color: var(--color-accent-800);
}
```

- [ ] **Step 4:** `npm test`, `npm run typecheck`, `npm run lint`, `npm run build` — all green.
- [ ] **Step 5: Stop for review**, then `git commit -m "feat: restyle the flashcard deck list" -m "Refs #24"`

---

### Task 2: Config form, generating view, panel flow

**Files:** `web/src/components/FlashcardConfigForm.tsx` (new), `web/src/components/FlashcardGenerating.tsx` (new), `web/src/components/FlashcardsPanel.tsx` (new), `web/src/components/FlashcardsPanel.test.tsx` (new), delete `web/src/components/FlashcardConfigModal.tsx`, `web/src/components/Flashcards.css`, `web/src/pages/VideoDetailPage.tsx`

**Interfaces — consumes:** Task 1's `FlashcardDeckList` (now given `onNew`), `FlashcardDraft`. **Produces:** `FlashcardsPanel({ videoId, segments, onSeek })`; `FlashcardReview` is rendered by the panel with the props it has today (`deckId`, `onSeek`, `onClose`) — Task 3 adds `segments`.

- [ ] **Step 1: Failing tests** — `web/src/components/FlashcardsPanel.test.tsx`:

```tsx
import { fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import type { FlashcardDeck } from '../types/flashcard'
import type { Segment } from '../types/video'
import { FlashcardsPanel } from './FlashcardsPanel'

afterEach(() => {
  vi.unstubAllGlobals()
})

const segments: Segment[] = [
  { id: 's1', label: 'Intro', summary: 'Opening.', start_time: 0, end_time: 60 },
  { id: 's2', label: 'Loops', summary: 'For and while.', start_time: 60, end_time: 300 },
]

const newDeck: FlashcardDeck = {
  id: 'd9',
  video_id: 'v1',
  title: 'Fresh deck',
  config: {},
  created_at: '2026-10-03T12:00:00Z',
  cards: [
    {
      id: 'c1',
      front: 'What does range(3) yield?',
      back: '0, 1 and 2.',
      segment_id: 's2',
      source_start_time: 95,
      difficulty: 'easy',
      order_index: 0,
      note: null,
    },
  ],
}

function stubApi(post: () => Promise<Response>) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') return post()
    if (url.endsWith('/flashcard-decks/d9')) return jsonResponse(200, newDeck)
    return jsonResponse(200, [])
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderPanel() {
  renderWithClient(<FlashcardsPanel videoId="v1" segments={segments} onSeek={() => {}} />)
}

it('goes from New deck through generating to reviewing the new deck', async () => {
  let resolve: (response: Response) => void = () => {}
  const fetchMock = stubApi(() => new Promise<Response>((r) => (resolve = r)))
  renderPanel()

  fireEvent.click(await screen.findByRole('button', { name: 'New deck' }))
  fireEvent.change(screen.getByRole('slider', { name: 'Number of cards' }), { target: { value: '20' } })
  fireEvent.click(screen.getByRole('button', { name: 'Generate 20 cards' }))

  expect(await screen.findByText('Generating deck…')).toBeTruthy()
  // The form is gone, so a second Generate can't fire.
  expect(screen.queryByRole('button', { name: /Generate/ })).toBeNull()
  const body = JSON.parse(String(fetchMock.mock.calls.find(([, i]) => i?.method === 'POST')?.[1]?.body))
  expect(body).toEqual({ count: 20, scope: 'whole_video', difficulty: 'mixed', style: 'mixed' })

  resolve(jsonResponse(201, newDeck))
  expect(await screen.findByText('What does range(3) yield?')).toBeTruthy()
})

it('sends segment ids only for selected topics, and disables Generate until one is picked', async () => {
  const fetchMock = stubApi(async () => jsonResponse(201, newDeck))
  renderPanel()
  fireEvent.click(await screen.findByRole('button', { name: 'New deck' }))

  fireEvent.click(screen.getByRole('radio', { name: 'Selected topics' }))
  expect(screen.getByRole('button', { name: 'Select at least one topic' })).toHaveProperty('disabled', true)
  fireEvent.click(screen.getByRole('checkbox', { name: 'Loops' }))
  expect(screen.getByText('1 of 2 selected')).toBeTruthy()
  fireEvent.change(screen.getByLabelText('Title (generated if blank)'), { target: { value: '   ' } })
  fireEvent.click(screen.getByRole('button', { name: 'Generate 12 cards' }))

  await screen.findByText('What does range(3) yield?')
  const body = JSON.parse(String(fetchMock.mock.calls.find(([, i]) => i?.method === 'POST')?.[1]?.body))
  expect(body).toEqual({ count: 12, scope: 'topics', segment_ids: ['s2'], difficulty: 'mixed', style: 'mixed' })
})

it('returns to the form with the error and the draft when generation fails', async () => {
  stubApi(async () => jsonResponse(422, { detail: 'Could not generate any flashcards for this configuration.' }))
  renderPanel()
  fireEvent.click(await screen.findByRole('button', { name: 'New deck' }))
  fireEvent.change(screen.getByLabelText('Title (generated if blank)'), { target: { value: 'My deck' } })
  fireEvent.click(screen.getByRole('button', { name: 'Generate 12 cards' }))

  expect(await screen.findByRole('alert')).toHaveProperty(
    'textContent',
    'Could not generate any flashcards for this configuration.',
  )
  expect(screen.getByLabelText('Title (generated if blank)')).toHaveProperty('value', 'My deck')
})

it('returns to the list from Cancel', async () => {
  stubApi(async () => jsonResponse(201, newDeck))
  renderPanel()
  fireEvent.click(await screen.findByRole('button', { name: 'New deck' }))
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(await screen.findByRole('heading', { name: 'Flashcard decks' })).toBeTruthy()
})
```

- [ ] **Step 2: Run, expect FAIL** (no `FlashcardsPanel`).

- [ ] **Step 3: `FlashcardGenerating.tsx`**

```tsx
import { useEffect, useState } from 'react'

// Generation is one request with no progress reported, so this says what is happening
// and how long it has taken rather than ticking invented steps.
export function FlashcardGenerating() {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <section className="fc-generating">
      <div aria-live="polite">
        <h4>Generating deck…</h4>
        <p className="text-muted">
          Retrieving passages, drafting cards and checking each one against the transcript.
        </p>
      </div>
      <p className="text-muted tabular fc-elapsed">{seconds}s elapsed</p>
    </section>
  )
}
```

- [ ] **Step 4: `FlashcardConfigForm.tsx`**

```tsx
import type { FlashcardDifficulty, FlashcardDraft, FlashcardScope, FlashcardStyle } from '../types/flashcard'
import type { Segment } from '../types/video'

interface SegProps<T extends string> {
  name: string
  label: string
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
}

function Seg<T extends string>({ name, label, value, options, onChange }: SegProps<T>) {
  return (
    <div className="fc-field">
      <h6 id={`fc-${name}-label`}>{label}</h6>
      <div className="seg" role="radiogroup" aria-labelledby={`fc-${name}-label`}>
        {options.map((option) => (
          <label className="seg-opt" key={option.value}>
            <input
              type="radio"
              name={`fc-${name}`}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            {option.label}
          </label>
        ))}
      </div>
    </div>
  )
}

const SCOPES: { value: FlashcardScope; label: string }[] = [
  { value: 'whole_video', label: 'Whole video' },
  { value: 'topics', label: 'Selected topics' },
]
const DIFFICULTIES: { value: FlashcardDifficulty; label: string }[] = [
  { value: 'easy', label: 'Easy' },
  { value: 'medium', label: 'Medium' },
  { value: 'hard', label: 'Hard' },
  { value: 'mixed', label: 'Mixed' },
]
const STYLES: { value: FlashcardStyle; label: string }[] = [
  { value: 'definition', label: 'Definition' },
  { value: 'concept', label: 'Concept' },
  { value: 'detail', label: 'Detail' },
  { value: 'mixed', label: 'Mixed' },
]

interface FlashcardConfigFormProps {
  draft: FlashcardDraft
  segments: Segment[]
  error: string | null
  onChange: (draft: FlashcardDraft) => void
  onSubmit: () => void
  onCancel: () => void
}

export function FlashcardConfigForm({
  draft,
  segments,
  error,
  onChange,
  onSubmit,
  onCancel,
}: FlashcardConfigFormProps) {
  const needsTopic = draft.scope === 'topics' && draft.segmentIds.length === 0

  function set<K extends keyof FlashcardDraft>(key: K, value: FlashcardDraft[K]) {
    onChange({ ...draft, [key]: value })
  }

  function toggleSegment(id: string) {
    set(
      'segmentIds',
      draft.segmentIds.includes(id) ? draft.segmentIds.filter((s) => s !== id) : [...draft.segmentIds, id],
    )
  }

  return (
    <form
      className="fc-config"
      onSubmit={(event) => {
        event.preventDefault()
        if (!needsTopic) onSubmit()
      }}
    >
      <h3>New deck</h3>

      <div className="fc-field">
        <h6>Cards</h6>
        <div className="fc-count">
          <input
            type="range"
            min={5}
            max={50}
            step={1}
            value={draft.count}
            aria-label="Number of cards"
            onChange={(event) => set('count', Number(event.target.value))}
          />
          <span className="tabular fc-count-value">{draft.count}</span>
        </div>
      </div>

      <Seg name="scope" label="Scope" value={draft.scope} options={SCOPES} onChange={(v) => set('scope', v)} />

      {draft.scope === 'topics' && (
        <div className="fc-field">
          <div className="fc-topics-head">
            <h6>Topics</h6>
            <h6 className="text-muted">
              {draft.segmentIds.length} of {segments.length} selected
            </h6>
          </div>
          {segments.length === 0 ? (
            <p className="text-muted">No topics available.</p>
          ) : (
            <div className="fc-topics">
              {segments.map((segment) => {
                const checked = draft.segmentIds.includes(segment.id)
                return (
                  <label key={segment.id} className={checked ? 'fc-topic fc-topic-checked' : 'fc-topic'}>
                    <input type="checkbox" checked={checked} onChange={() => toggleSegment(segment.id)} />
                    <span aria-hidden="true" className="fc-topic-mark">
                      {checked ? '■' : '□'}
                    </span>
                    {segment.label}
                  </label>
                )
              })}
            </div>
          )}
        </div>
      )}

      <Seg
        name="difficulty"
        label="Difficulty"
        value={draft.difficulty}
        options={DIFFICULTIES}
        onChange={(v) => set('difficulty', v)}
      />
      <Seg name="style" label="Style" value={draft.style} options={STYLES} onChange={(v) => set('style', v)} />

      <div className="field">
        <label htmlFor="fc-title">Title (generated if blank)</label>
        <input
          id="fc-title"
          className="input"
          value={draft.title}
          onChange={(event) => set('title', event.target.value)}
        />
      </div>

      {error && (
        <p role="alert" className="fc-error">
          {error}
        </p>
      )}

      <div className="fc-actions">
        <button type="submit" className="btn btn-primary" disabled={needsTopic}>
          {needsTopic ? 'Select at least one topic' : `Generate ${draft.count} cards`}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  )
}
```

(The `SCOPES`/`DIFFICULTIES`/`STYLES` constants are module-level `const`s, not exports — fine for `only-export-components`.)

- [ ] **Step 5: `FlashcardsPanel.tsx`**

```tsx
import { useState } from 'react'
import { useCreateFlashcardDeck } from '../hooks/useFlashcards'
import type { FlashcardConfig, FlashcardDraft } from '../types/flashcard'
import type { Segment } from '../types/video'
import { FlashcardConfigForm } from './FlashcardConfigForm'
import { FlashcardDeckList } from './FlashcardDeckList'
import { FlashcardGenerating } from './FlashcardGenerating'
import { FlashcardReview } from './FlashcardReview'

const DEFAULT_DRAFT: FlashcardDraft = {
  count: 12,
  scope: 'whole_video',
  segmentIds: [],
  difficulty: 'mixed',
  style: 'mixed',
  title: '',
}

function toConfig(draft: FlashcardDraft): FlashcardConfig {
  const title = draft.title.trim()
  return {
    count: draft.count,
    scope: draft.scope,
    ...(draft.scope === 'topics' ? { segment_ids: draft.segmentIds } : {}),
    difficulty: draft.difficulty,
    style: draft.style,
    ...(title ? { title } : {}),
  }
}

type View = { name: 'list' } | { name: 'config' } | { name: 'review'; deckId: string }

interface FlashcardsPanelProps {
  videoId: string
  segments: Segment[]
  onSeek: (seconds: number) => void
}

// "Generating" is the config view while the create request is pending, so a failure
// lands back on the form with its error and the draft intact.
export function FlashcardsPanel({ videoId, segments, onSeek }: FlashcardsPanelProps) {
  const createDeck = useCreateFlashcardDeck(videoId)
  const [view, setView] = useState<View>({ name: 'list' })
  const [draft, setDraft] = useState<FlashcardDraft>(DEFAULT_DRAFT)

  function openConfig() {
    createDeck.reset()
    setView({ name: 'config' })
  }

  async function generate() {
    try {
      const deck = await createDeck.mutateAsync(toConfig(draft))
      setDraft((previous) => ({ ...previous, title: '', segmentIds: [] }))
      setView({ name: 'review', deckId: deck.id })
    } catch {
      // createDeck.error renders on the form.
    }
  }

  if (view.name === 'review') {
    return (
      <FlashcardReview
        key={view.deckId}
        deckId={view.deckId}
        onSeek={onSeek}
        onClose={() => setView({ name: 'list' })}
      />
    )
  }
  if (view.name === 'config') {
    return createDeck.isPending ? (
      <FlashcardGenerating />
    ) : (
      <FlashcardConfigForm
        draft={draft}
        segments={segments}
        error={createDeck.error?.message ?? null}
        onChange={setDraft}
        onSubmit={generate}
        onCancel={() => setView({ name: 'list' })}
      />
    )
  }
  return (
    <FlashcardDeckList
      videoId={videoId}
      onNew={openConfig}
      onReview={(deckId) => setView({ name: 'review', deckId })}
    />
  )
}
```

Make `FlashcardDeckList`'s `onNew` required now (`onNew: () => void`, drop the `{onNew && …}` guard) and pass `onNew={() => {}}` in its tests.

- [ ] **Step 6: Page wiring** — in `VideoDetailPage.tsx`, the `flashcards` prop becomes `<FlashcardsPanel videoId={video.id} segments={video.segments} onSeek={seek} />`; remove `reviewingDeckId`, and the `FlashcardConfigModal`/`FlashcardDeckList`/`FlashcardReview` imports. `git rm web/src/components/FlashcardConfigModal.tsx`. Add to `VideoDetailPage.test.tsx`:

```tsx
it('renders the flashcards panel in its tab', async () => {
  renderPage(video({}))
  fireEvent.click(await screen.findByRole('tab', { name: 'Flashcards' }))
  expect(await screen.findByRole('heading', { name: 'Flashcard decks' })).toBeTruthy()
})
```

- [ ] **Step 7: CSS** — append to `Flashcards.css`:

```css
.fc-config,
.fc-generating {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.fc-config h3,
.fc-generating h4 {
  margin: 0;
}

.fc-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.fc-field h6 {
  margin: 0;
}

.fc-count {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.fc-count input {
  flex: 1;
  accent-color: var(--color-accent);
}

.fc-count-value {
  min-width: 2ch;
  font-family: var(--font-heading);
  font-weight: 600;
  font-size: 20px;
}

/* The native radios inside .seg are hidden by industry.css; show keyboard focus. */
.fc-config .seg-opt:has(input:focus-visible),
.fc-topic:has(input:focus-visible) {
  outline: 2px solid var(--color-accent);
  outline-offset: -2px;
}

.fc-topics-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
}

.fc-topics {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.fc-topic {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2);
  border: 1px solid var(--color-divider);
  cursor: pointer;
}

.fc-topic-checked {
  border-color: var(--color-accent);
  background: var(--color-accent-100);
}

.fc-topic input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
  pointer-events: none;
}

.fc-topic-mark {
  color: var(--color-accent);
}

.fc-actions {
  display: flex;
  gap: var(--space-2);
}

.fc-generating p {
  margin: 0;
}

.fc-elapsed {
  font-size: 13px;
}
```

(Dark mode: `--color-accent-100` is redefined by the theme; confirm the checked row reads in the Task 4 browser check.)

- [ ] **Step 8:** `npm test`, `typecheck`, `lint`, `build` — green.
- [ ] **Step 9: Stop for review**, then `git commit -m "feat: move flashcard config and generation into the tab" -m "Refs #24"`

---

### Task 3: Review

**Files:** `web/src/components/FlashcardReview.tsx`, `web/src/components/FlashcardReview.test.tsx` (new), `web/src/components/Flashcards.css`, `web/src/components/FlashcardsPanel.tsx` (pass `segments`), `docs/superpowers/specs/2026-10-03-flashcards-tab-design.md` (keyboard wording)

**Interfaces — produces:** `FlashcardReview({ deckId, segments, onSeek, onClose })`.

- [ ] **Step 1: Failing tests** — `web/src/components/FlashcardReview.test.tsx`:

```tsx
import { fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import type { Flashcard, FlashcardDeck } from '../types/flashcard'
import type { Segment } from '../types/video'
import { FlashcardReview } from './FlashcardReview'

afterEach(() => {
  vi.unstubAllGlobals()
})

const segments: Segment[] = [{ id: 's2', label: 'Loops', summary: 'x', start_time: 60, end_time: 300 }]

function card(overrides: Partial<Flashcard>): Flashcard {
  return {
    id: 'c1',
    front: 'Front one',
    back: 'Back one',
    segment_id: 's2',
    source_start_time: 95,
    difficulty: 'easy',
    order_index: 0,
    note: null,
    ...overrides,
  }
}

function renderDeck(cards: Flashcard[], onSeek = vi.fn()) {
  const deck: FlashcardDeck = { id: 'd1', video_id: 'v1', title: 'Loops deck', config: {}, created_at: '', cards }
  vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, deck)))
  renderWithClient(<FlashcardReview deckId="d1" segments={segments} onSeek={onSeek} onClose={() => {}} />)
  return onSeek
}

const twoCards = [
  card({ note: 'The video says 0 to 3; the speaker means 0 to 2.' }),
  card({ id: 'c2', front: 'Front two', back: 'Back two', segment_id: null, source_start_time: null, difficulty: null }),
]

it('shows the position, the topic and a progress strip', async () => {
  renderDeck(twoCards)
  expect(await screen.findByText('Front one')).toBeTruthy()
  expect(screen.getByText('Card 1 of 2')).toBeTruthy()
  expect(screen.getByText('Loops')).toBeTruthy()
  const cells = document.querySelectorAll('.fc-cell')
  expect([...cells].map((c) => c.className)).toEqual(['fc-cell fc-cell-current', 'fc-cell'])
})

it('reveals the back and the note with Space, and moves on with ArrowRight', async () => {
  renderDeck(twoCards)
  const section = await screen.findByRole('region', { name: 'Flashcard review' })
  await screen.findByText('Front one')

  fireEvent.keyDown(section, { key: ' ' })
  expect(screen.getByText('Back one')).toBeTruthy()
  expect(screen.getByText('The video says 0 to 3; the speaker means 0 to 2.')).toBeTruthy()

  fireEvent.keyDown(section, { key: 'ArrowRight' })
  expect(screen.getByText('Front two')).toBeTruthy()
  expect(screen.queryByText('Back two')).toBeNull()
  expect([...document.querySelectorAll('.fc-cell')].map((c) => c.className)).toEqual([
    'fc-cell fc-cell-past',
    'fc-cell fc-cell-current',
  ])
})

it('still moves with the arrows when a button has focus', async () => {
  renderDeck(twoCards)
  const next = await screen.findByRole('button', { name: 'Next →' })
  fireEvent.keyDown(next, { key: 'ArrowRight' })
  expect(screen.getByText('Front two')).toBeTruthy()
})

it('seeks from Jump without hiding the answer', async () => {
  const onSeek = renderDeck(twoCards)
  fireEvent.click(await screen.findByText('Front one'))
  fireEvent.click(screen.getByRole('button', { name: 'Jump to 1:35' }))
  expect(onSeek).toHaveBeenCalledWith(95)
  expect(screen.getByText('Back one')).toBeTruthy()
})

it('leaves out Jump and the topic when a card has neither, and disables the ends', async () => {
  renderDeck(twoCards)
  expect(await screen.findByRole('button', { name: '← Previous' })).toHaveProperty('disabled', true)
  fireEvent.click(screen.getByRole('button', { name: 'Next →' }))
  expect(screen.getByRole('button', { name: 'Next →' })).toHaveProperty('disabled', true)
  fireEvent.click(screen.getByRole('button', { name: 'Click to reveal answer' }))
  expect(screen.getByText('Back two')).toBeTruthy()
  expect(screen.queryByRole('button', { name: /Jump to/ })).toBeNull()
  expect(screen.queryByText('Loops')).toBeNull()
})
```

(Note: the strip-cell assertions match on exact class strings; keep the class composition exactly as in Step 3.)

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: `FlashcardReview.tsx`**

```tsx
import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useFlashcardDeckQuery } from '../hooks/useFlashcards'
import { formatTime } from '../lib/time'
import type { Segment } from '../types/video'
import { Corners } from './Corners'
import './Flashcards.css'

interface FlashcardReviewProps {
  deckId: string
  segments: Segment[]
  onSeek: (seconds: number) => void
  onClose: () => void
}

// Parent must render this with `key={deckId}` so switching decks remounts it
// with fresh index/revealed state, instead of syncing it via an effect.
export function FlashcardReview({ deckId, segments, onSeek, onClose }: FlashcardReviewProps) {
  const { data: deck, isLoading, error } = useFlashcardDeckQuery(deckId)
  const [index, setIndex] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const sectionRef = useRef<HTMLElement>(null)
  const cards = deck?.cards ?? []
  const card = cards[index]

  // Focus the review once the deck is in, so the shortcuts work straight away.
  useEffect(() => {
    if (deck) sectionRef.current?.focus()
  }, [deck])

  function goTo(next: number) {
    if (next < 0 || next >= cards.length) return
    setIndex(next)
    setRevealed(false)
  }

  // Scoped to this section, so it never fires from another tab's input. Space/Enter
  // defer to a focused control (Jump, Next…); the arrows always move.
  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (!card) return
    const onControl = (event.target as HTMLElement).closest('button, a, input, textarea, select')
    if ((event.key === ' ' || event.key === 'Enter') && !onControl) {
      event.preventDefault()
      setRevealed((r) => !r)
    } else if (event.key === 'ArrowRight') {
      event.preventDefault()
      goTo(index + 1)
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault()
      goTo(index - 1)
    }
  }

  const label = card ? segments.find((s) => s.id === card.segment_id)?.label : undefined
  const start = card?.source_start_time ?? null

  return (
    <section
      ref={sectionRef}
      tabIndex={-1}
      className="fc-review"
      aria-label="Flashcard review"
      onKeyDown={handleKeyDown}
    >
      <div className="fc-list-head">
        <h3>{deck?.title ?? 'Deck'}</h3>
        <button type="button" className="btn btn-ghost" onClick={onClose}>
          Close
        </button>
      </div>
      {isLoading && <p className="text-muted">Loading…</p>}
      {error && (
        <p role="alert" className="fc-error">
          {error.message}
        </p>
      )}
      {deck && cards.length === 0 && <p className="text-muted">This deck has no cards.</p>}
      {card && (
        <>
          <div className="fc-position">
            <h6>
              Card {index + 1} of {cards.length}
            </h6>
            {card.difficulty && <span className="tag tag-neutral fc-tag">{card.difficulty}</span>}
          </div>
          <div className="fc-strip" aria-hidden="true">
            {cards.map((c, i) => (
              <span
                key={c.id}
                className={i < index ? 'fc-cell fc-cell-past' : i === index ? 'fc-cell fc-cell-current' : 'fc-cell'}
              />
            ))}
          </div>
          <div className="blueprint fc-card" onClick={() => setRevealed((r) => !r)}>
            <Corners />
            {label && <span className="fc-kicker">{label}</span>}
            <p className="fc-front">{card.front}</p>
            {revealed && (
              <div className="fc-answer">
                <p className="fc-back">{card.back}</p>
                {card.note && <p className="text-muted fc-note">{card.note}</p>}
                {start !== null && (
                  <button
                    type="button"
                    className="btn btn-ghost fc-jump"
                    onClick={(event) => {
                      event.stopPropagation()
                      onSeek(start)
                    }}
                  >
                    Jump to {formatTime(start)}
                  </button>
                )}
              </div>
            )}
            <button
              type="button"
              className="fc-toggle"
              aria-expanded={revealed}
              onClick={(event) => {
                event.stopPropagation()
                setRevealed((r) => !r)
              }}
            >
              {revealed ? 'Hide answer' : 'Click to reveal answer'}
            </button>
          </div>
          <div className="fc-nav">
            <button type="button" className="btn btn-secondary" onClick={() => goTo(index - 1)} disabled={index === 0}>
              ← Previous
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => goTo(index + 1)}
              disabled={index === cards.length - 1}
            >
              Next →
            </button>
          </div>
        </>
      )}
    </section>
  )
}
```

`FlashcardsPanel.tsx`: pass `segments={segments}` to `FlashcardReview`.

- [ ] **Step 4: CSS** — append to `Flashcards.css`:

```css
.fc-review {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  outline: none;
}

.fc-position {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.fc-position h6 {
  margin: 0;
}

.fc-tag {
  text-transform: uppercase;
}

.fc-strip {
  display: flex;
  gap: 3px;
}

.fc-cell {
  flex: 1;
  height: 4px;
  border: 1px solid var(--color-divider);
}

.fc-cell-past {
  background: var(--color-accent-300);
}

.fc-cell-current {
  background: var(--color-accent);
}

.fc-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-height: 250px;
  padding: var(--space-8) var(--space-6);
  cursor: pointer;
}

.fc-card:hover {
  background: color-mix(in srgb, var(--color-text) 3%, transparent);
}

.fc-kicker {
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-accent);
}

.fc-front {
  margin: 0;
  font-family: var(--font-heading);
  font-weight: 600;
  font-size: 26px;
  line-height: 1.16;
  overflow-wrap: anywhere;
}

.fc-answer {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-3);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-divider);
}

.fc-back {
  margin: 0;
  font-size: 15px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.fc-note {
  margin: 0;
  font-size: 13px;
}

/* Pinned to the bottom of the card. */
.fc-toggle {
  margin-top: auto;
  align-self: flex-start;
  padding: 0;
  border: none;
  background: transparent;
  color: color-mix(in srgb, var(--color-text) 55%, transparent);
  font: inherit;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  cursor: pointer;
}

.fc-nav {
  display: flex;
  gap: var(--space-2);
}

.fc-nav .btn {
  flex: 1;
}
```

- [ ] **Step 5: Spec** — in the spec's Review "Keyboard" bullet, replace "ignored when the event's target is a button, link or input, so Enter/Space on a focused button keep their native meaning" with "Space/Enter are ignored when the event's target is a button, link or input, so they keep their native meaning there; the arrows always move (focus often sits on Next after a click)."

- [ ] **Step 6:** `npm test`, `typecheck`, `lint`, `build` — green.
- [ ] **Step 7: Stop for review**, then `git commit -m "feat: restyle flashcard review with keyboard and slip notes" -m "Refs #24"`

---

### Task 4: Browser check

No commit unless it finds a fix (its own commit, own review stop).

- [ ] `docker compose restart web`. On the Python video (`0b3ee81c`), light and dark, 1440×900 and 420px:
  - deck list: existing decks show count, relative date and summary;
  - New deck → change count, pick "Selected topics" with none (button disabled, label), pick one, title blank → Generate 5 cards → "Generating deck…" with the counter → review opens (one real generation, cents);
  - review with the mouse and the keyboard (Space, arrows, Tab to Jump + Enter seeks without flipping); a card with a `note` if one appears; the strip advances; long text wraps;
  - checked topic rows read in dark mode (`--color-accent-100`);
  - type a title in config, switch to Chat and back → still there; with a deck open in review, type Space and arrows in the chat input → the card doesn't change;
  - Cancel; delete a deck (confirm cancel, then confirm).
- [ ] Clean `.playwright-mcp/` afterwards.
