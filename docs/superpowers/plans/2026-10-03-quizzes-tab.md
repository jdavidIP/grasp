# Quizzes Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Quizzes tab becomes one panel (list → config → generating → take → results, plus history and attempt detail) in the Industry design; the quiz list gains `attempt_count`; the flashcards form pieces become shared. Sub-project 5 of 5 for #24 — its PR closes #24.

**Architecture:** `QuizzesPanel` owns the view and the config draft, mirroring `FlashcardsPanel` ("generating" = config view while the create mutation is pending). `QuizTake` hands its graded result up; `QuizResults` renders a result for both a fresh submit and an attempt fetched from history. Existing hooks unchanged; one grouped-query addition on the backend.

**Tech Stack:** FastAPI + SQLAlchemy (one query), pytest; React 19, TypeScript strict, TanStack Query 5, Vitest 5 + RTL + jsdom.

**Spec:** `docs/superpowers/specs/2026-10-03-quizzes-tab-design.md`

## Global Constraints

- **Branch:** `feat/24-quizzes-tab`. One commit per task. **Before each commit, show the change and wait for the go-ahead** (only "skip my review" waives it). No `Co-Authored-By`. Conventional messages ending with `Refs #24`.
- **Commands** in containers: `docker compose exec -T api …` / `docker compose exec -T web …`; restart the container before browser checks. **Never run tools the repo doesn't use** (no prettier); match the style: single quotes, no semicolons (TS), ruff (Python).
- Tests share the dev database: only touch rows the test created (`test-` videos).
- Component files export only components; helpers in `web/src/lib/`, types in `web/src/types/`. No `any`. Industry tokens only; quiz classes `.qz-*`, shared form classes `.form-*`.
- **Fixed copy:** "Quizzes", "New quiz", "No quizzes yet.", "Best {n}%", "Never attempted", "{n} questions · {n} attempts" (singulars), "Take", "History", "Delete", `Delete the quiz "{title}"? This deletes its attempt history too, and cannot be undone.`, "Questions", "Question types", "Multiple choice" / "Exactly one correct option", "Select all that apply" / "All-or-nothing grading", "True / false" / "Always two options", "At least one type is required.", "Options per question", "Generate {n} questions", "Generating quiz…", "Multiple choice — one answer", "{n} of {m} answered. Unanswered questions count as incorrect.", "Submit", "Grading…", "Leave this quiz? Your answers so far will be lost.", "{k} of {m} questions are unanswered and will count as incorrect. Submit anyway?", "{c} of {t} correct · all-or-nothing, no partial credit", "correct answer", "your answer", "your answer · correct", "You skipped this question.", "Retake", "Attempt history", "← Attempts", "Take it again", "Completed", "Correct", "Score", "No attempts yet.", "View attempt from {relative}", "This quiz has no questions."

## Review Focus

1. **Answer key before submit** — nothing in the take view may request or hold `is_correct`/`explanation`; only `GET /quizzes/{id}` (key withheld) is used until submit. Covered by the existing backend test; check the take code by reading it.
2. **Double Submit** — Submit is disabled while grading; a second click can't post a second attempt. Tested in Task 4.
3. **A half-taken quiz** — switching tabs keeps answers (panels mounted); Close with answers asks first. Tested in Task 4.
4. **Retake starts empty** — a retake must not show the previous selections. Tested in Task 4.
5. **Long prompts/options and null times** — wrap (`overflow-wrap: anywhere`); a result without `source_start_time` shows no Jump. Tested / browser-checked in Tasks 4–5.

---

## File Structure

| File | Responsibility |
|---|---|
| `api/app/schemas/quiz.py`, `api/app/routers/quizzes.py`, `api/tests/test_quizzes.py`, `docs/API.md` | `attempt_count` |
| `web/src/components/SegmentedControl.tsx`, `TopicPicker.tsx`, `CountSlider.tsx`, `GeneratingStatus.tsx`, `Forms.css` | shared form pieces |
| `web/src/components/FlashcardConfigForm.tsx`, `FlashcardsPanel.tsx`, `Flashcards.css` (`FlashcardGenerating.tsx` deleted) | use them |
| `web/src/types/quiz.ts` | `attempt_count`, `QuizDraft` |
| `web/src/components/QuizzesPanel.tsx`, `QuizConfigForm.tsx` (`QuizConfigModal.tsx` deleted) | panel, form |
| `web/src/components/QuizList.tsx`, `QuizTake.tsx`, `QuizResults.tsx`, `QuizAttemptHistory.tsx`, `Quizzes.css` | views |
| `web/src/pages/VideoDetailPage.tsx` | Quizzes tab renders the panel |

---

### Task 1: `attempt_count` on the quiz list

**Files:** `api/app/schemas/quiz.py`, `api/app/routers/quizzes.py`, `api/tests/test_quizzes.py`, `docs/API.md`

- [ ] **Step 1: Failing test** — append to `api/tests/test_quizzes.py`:

```python
async def test_quiz_list_counts_attempts():
    video_id = await _create_ready_video()
    async with _client() as client:
        quiz = await _create_quiz(client, video_id)
        listing = (await client.get(f"/api/videos/{video_id}/quizzes")).json()
        assert listing[0]["attempt_count"] == 0

        for _ in range(2):
            response = await client.post(f"/api/quizzes/{quiz['id']}/attempts", json={"answers": []})
            assert response.status_code == 201

        listing = (await client.get(f"/api/videos/{video_id}/quizzes")).json()
        assert listing[0]["attempt_count"] == 2
```

- [ ] **Step 2: Run, expect FAIL** (`KeyError: 'attempt_count'`): `docker compose exec -T api pytest tests/test_quizzes.py -k counts -q`

- [ ] **Step 3: Implement.** Schema: `QuizListItem.attempt_count: int` after `best_score`. Router `list_quizzes`:

```python
    stats_result = await db.execute(
        select(QuizAttempt.quiz_id, func.max(QuizAttempt.score), func.count(QuizAttempt.id))
        .where(QuizAttempt.quiz_id.in_([q.id for q in quizzes]))
        .group_by(QuizAttempt.quiz_id)
    )
    stats = {quiz_id: (float(best), count) for quiz_id, best, count in stats_result.all()}
```

and in the list item: `best_score=stats[quiz.id][0] if quiz.id in stats else None, attempt_count=stats[quiz.id][1] if quiz.id in stats else 0,` (replace the old `best_result`/`best_scores`).

`docs/API.md`, `GET /videos/{id}/quizzes`: "Quizzes for a video, each with `question_count`, `best_score` (fraction 0–1, `null` if never attempted) and `attempt_count`."

- [ ] **Step 4:** `pytest tests/test_quizzes.py -q`, then `ruff check .`, `ruff format --check .`, full `pytest`.
- [ ] **Step 5: Stop for review**, then `git commit -m "feat: count attempts in the quiz list" -m "Refs #24"`

---

### Task 2: Shared form pieces

**Files:** create `web/src/components/SegmentedControl.tsx`, `TopicPicker.tsx`, `CountSlider.tsx`, `GeneratingStatus.tsx`, `Forms.css`; modify `FlashcardConfigForm.tsx`, `FlashcardsPanel.tsx`, `Flashcards.css`; delete `FlashcardGenerating.tsx`.

**Interfaces — produces:**
- `SegmentedControl<T extends string>({ name, label, value, options: {value: T; label: string}[], onChange })`
- `TopicPicker({ segments, selectedIds, onToggle(id) })`
- `CountSlider({ label, ariaLabel, min, max, value, onChange(n) })`
- `GeneratingStatus({ heading })`

This is a refactor: the flashcards tests are the safety net and must pass **unchanged**. No new tests.

- [ ] **Step 1:** Run `npm test` and note it green (70).

- [ ] **Step 2: Create the components** (moved code, renamed classes):

`SegmentedControl.tsx` — `Seg` from `FlashcardConfigForm.tsx`, exported, wrapper class `form-field`, ids `form-${name}-label`, radio names `form-${name}`:

```tsx
import './Forms.css'

interface SegmentedControlProps<T extends string> {
  name: string
  label: string
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
}

export function SegmentedControl<T extends string>({ name, label, value, options, onChange }: SegmentedControlProps<T>) {
  return (
    <div className="form-field">
      <h6 id={`form-${name}-label`}>{label}</h6>
      <div className="seg" role="radiogroup" aria-labelledby={`form-${name}-label`}>
        {options.map((option) => (
          <label className="seg-opt" key={option.value}>
            <input
              type="radio"
              name={`form-${name}`}
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
```

(The radio `name` is shared page-wide: both config forms stay mounted, so the two forms must not share a group name. **Prefix `name` at the call site** — flashcards pass `fc-scope`, quizzes `qz-scope`, etc.)

`TopicPicker.tsx`:

```tsx
import type { Segment } from '../types/video'
import './Forms.css'

interface TopicPickerProps {
  segments: Segment[]
  selectedIds: string[]
  onToggle: (id: string) => void
}

export function TopicPicker({ segments, selectedIds, onToggle }: TopicPickerProps) {
  return (
    <div className="form-field">
      <div className="form-topics-head">
        <h6>Topics</h6>
        <h6 className="text-muted">
          {selectedIds.length} of {segments.length} selected
        </h6>
      </div>
      {segments.length === 0 ? (
        <p className="text-muted">No topics available.</p>
      ) : (
        <div className="form-topics">
          {segments.map((segment) => {
            const checked = selectedIds.includes(segment.id)
            return (
              <label key={segment.id} className={checked ? 'form-topic form-topic-checked' : 'form-topic'}>
                <input type="checkbox" checked={checked} onChange={() => onToggle(segment.id)} />
                <span aria-hidden="true" className="form-topic-mark">
                  {checked ? '■' : '□'}
                </span>
                {segment.label}
              </label>
            )
          })}
        </div>
      )}
    </div>
  )
}
```

`CountSlider.tsx`:

```tsx
import './Forms.css'

interface CountSliderProps {
  label: string
  ariaLabel: string
  min: number
  max: number
  value: number
  onChange: (value: number) => void
}

export function CountSlider({ label, ariaLabel, min, max, value, onChange }: CountSliderProps) {
  return (
    <div className="form-field">
      <h6>{label}</h6>
      <div className="form-count">
        <input
          type="range"
          min={min}
          max={max}
          step={1}
          value={value}
          aria-label={ariaLabel}
          onChange={(event) => onChange(Number(event.target.value))}
        />
        <span className="tabular form-count-value">{value}</span>
      </div>
    </div>
  )
}
```

`GeneratingStatus.tsx` — `FlashcardGenerating` with `heading` prop, classes `form-generating` / `form-elapsed` (keep its comment).

`Forms.css` — move from `Flashcards.css` (renaming `fc-` → `form-`): `.fc-config`+`.fc-generating` (→ `.form`, `.form-generating`), their `h3`/`h4` margins, `.fc-field` (+ `h6`), `.fc-count` (+ `input`, `-value`), `.fc-topic:has(input:focus-visible)`, `.fc-topics-head`, `.fc-topics`, `.fc-topic` (+ `-checked`, `input`, `-mark`), `.fc-actions`, `.fc-generating p`, `.fc-elapsed`. Also move `.fc-error` → `.form-error` there and keep using it from flashcards. Delete the moved rules from `Flashcards.css`.

- [ ] **Step 3: Use them** — `FlashcardConfigForm.tsx`: delete the local `Seg`; `<form className="form" …>`; Cards → `<CountSlider label="Cards" ariaLabel="Number of cards" min={5} max={50} value={draft.count} onChange={(n) => set('count', n)} />`; `<SegmentedControl name="fc-scope" …>`, `fc-difficulty`, `fc-style`; the topics block → `{draft.scope === 'topics' && <TopicPicker segments={segments} selectedIds={draft.segmentIds} onToggle={toggleSegment} />}`; `.fc-actions` → `.form-actions`, `.fc-error` → `.form-error`. `FlashcardsPanel.tsx`: `<GeneratingStatus heading="Generating deck…" />`. Replace remaining `fc-error` uses (DeckList, Review) with `form-error` (import `./Forms.css` where needed). `git rm web/src/components/FlashcardGenerating.tsx`.

- [ ] **Step 4:** `npm test` (70, unchanged), `typecheck`, `lint`, `build`. `docker compose restart web`; glance at the flashcards config form in the browser — it must look the same.
- [ ] **Step 5: Stop for review**, then `git commit -m "refactor: share the config form pieces between tabs" -m "Refs #24"`

---

### Task 3: Quiz list, config form, panel shell

**Files:** `web/src/types/quiz.ts`, `web/src/components/QuizList.tsx` (+ new `QuizList.test.tsx`), `QuizConfigForm.tsx` (new), `QuizzesPanel.tsx` (+ new `QuizzesPanel.test.tsx`), `Quizzes.css` (new), delete `QuizConfigModal.tsx`, `web/src/pages/VideoDetailPage.tsx` (+ test)

**Interfaces — produces:** `QuizzesPanel({ videoId, segments, onSeek })` with views `list | config | take | history`, rendering today's `QuizTake` / `QuizAttemptHistory` unchanged for `take` / `history` (Task 4 replaces them). `QuizList({ videoId, onNew, onTake, onHistory })`.

- [ ] **Step 1: Types** — `QuizListItem.attempt_count: number`; add:

```ts
// The config form's working state; `QuizzesPanel` turns it into a QuizConfig.
export interface QuizDraft {
  count: number
  scope: QuizScope
  segmentIds: string[]
  questionTypes: QuestionType[]
  optionsPerQuestion: number
  difficulty: QuizDifficulty
  title: string
}
```

- [ ] **Step 2: Failing tests**

`web/src/components/QuizList.test.tsx`:

```tsx
import { fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import type { QuizListItem } from '../types/quiz'
import { QuizList } from './QuizList'

afterEach(() => {
  vi.unstubAllGlobals()
})

function quiz(overrides: Partial<QuizListItem>): QuizListItem {
  return {
    id: 'q1',
    video_id: 'v1',
    title: 'Loops quiz',
    config: {},
    created_at: '2026-10-03T12:00:00Z',
    question_count: 6,
    best_score: 0.834,
    attempt_count: 3,
    ...overrides,
  }
}

function stubQuizzes(quizzes: QuizListItem[]) {
  const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => jsonResponse(200, quizzes))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderList() {
  renderWithClient(<QuizList videoId="v1" onNew={() => {}} onTake={() => {}} onHistory={() => {}} />)
}

it('shows the best score and the question and attempt counts', async () => {
  stubQuizzes([quiz({}), quiz({ id: 'q2', title: 'Fresh', question_count: 1, best_score: null, attempt_count: 0 })])
  renderList()
  expect(await screen.findByText('Best 83%')).toBeTruthy()
  expect(screen.getByText('6 questions · 3 attempts')).toBeTruthy()
  expect(screen.getByText('Never attempted')).toBeTruthy()
  expect(screen.getByText('1 question · 0 attempts')).toBeTruthy()
})

it('sends nothing when Delete is cancelled', async () => {
  const fetchMock = stubQuizzes([quiz({})])
  vi.stubGlobal('confirm', vi.fn(() => false))
  renderList()
  fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
})
```

`web/src/components/QuizzesPanel.test.tsx` (config + flow; `QuizTake` is still today's component here):

```tsx
import { fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import type { Quiz } from '../types/quiz'
import type { Segment } from '../types/video'
import { QuizzesPanel } from './QuizzesPanel'

afterEach(() => {
  vi.unstubAllGlobals()
})

const segments: Segment[] = [
  { id: 's1', label: 'Intro', summary: 'x', start_time: 0, end_time: 60 },
  { id: 's2', label: 'Loops', summary: 'y', start_time: 60, end_time: 300 },
]

const newQuiz: Quiz = {
  id: 'q9',
  video_id: 'v1',
  title: 'Fresh quiz',
  config: {},
  created_at: '2026-10-03T12:00:00Z',
  questions: [
    {
      id: 'qq1',
      order_index: 0,
      question_type: 'true_false',
      prompt: 'Python lists use square brackets.',
      difficulty: 'easy',
      options: [
        { id: 'o1', text: 'True', order_index: 0 },
        { id: 'o2', text: 'False', order_index: 1 },
      ],
    },
  ],
}

function stubApi(post: () => Promise<Response>) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') return post()
    if (url.endsWith('/quizzes/q9')) return jsonResponse(200, newQuiz)
    return jsonResponse(200, [])
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function postedBody(fetchMock: ReturnType<typeof stubApi>): unknown {
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')
  return JSON.parse(String(call?.[1]?.body))
}

async function openConfig() {
  renderWithClient(<QuizzesPanel videoId="v1" segments={segments} onSeek={() => {}} />)
  fireEvent.click(await screen.findByRole('button', { name: 'New quiz' }))
}

it('goes from New quiz through generating to taking the new quiz, with the default payload', async () => {
  let resolve: (response: Response) => void = () => {}
  const fetchMock = stubApi(() => new Promise<Response>((r) => (resolve = r)))
  await openConfig()
  fireEvent.click(screen.getByRole('button', { name: 'Generate 6 questions' }))

  expect(await screen.findByText('Generating quiz…')).toBeTruthy()
  expect(postedBody(fetchMock)).toEqual({
    count: 6,
    scope: 'whole_video',
    question_types: ['multiple_choice', 'multi_select', 'true_false'],
    options_per_question: 4,
    difficulty: 'mixed',
  })
  resolve(jsonResponse(201, newQuiz))
  expect(await screen.findByText('Python lists use square brackets.')).toBeTruthy()
})

it('keeps the last question type checked and drops options per question for true/false only', async () => {
  const fetchMock = stubApi(async () => jsonResponse(201, newQuiz))
  await openConfig()
  fireEvent.click(screen.getByRole('checkbox', { name: /^Multiple choice/ }))
  fireEvent.click(screen.getByRole('checkbox', { name: /^Select all that apply/ }))
  const trueFalse = screen.getByRole('checkbox', { name: /^True \/ false/ })
  expect(trueFalse).toHaveProperty('disabled', true)
  expect(screen.getByText('At least one type is required.')).toBeTruthy()
  expect(screen.queryByRole('radiogroup', { name: 'Options per question' })).toBeNull()

  fireEvent.click(screen.getByRole('radio', { name: 'Selected topics' }))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Loops' }))
  fireEvent.click(screen.getByRole('button', { name: 'Generate 6 questions' }))

  await screen.findByText('Python lists use square brackets.')
  expect(postedBody(fetchMock)).toEqual({
    count: 6,
    scope: 'topics',
    segment_ids: ['s2'],
    question_types: ['true_false'],
    difficulty: 'mixed',
  })
})

it('returns to the form with the error and the draft when generation fails', async () => {
  stubApi(async () => jsonResponse(422, { detail: 'Could not generate any questions for this configuration.' }))
  await openConfig()
  fireEvent.change(screen.getByLabelText('Title (generated if blank)'), { target: { value: 'Mine' } })
  fireEvent.click(screen.getByRole('button', { name: 'Generate 6 questions' }))

  expect(await screen.findByRole('alert')).toHaveProperty(
    'textContent',
    'Could not generate any questions for this configuration.',
  )
  expect(screen.getByLabelText('Title (generated if blank)')).toHaveProperty('value', 'Mine')
})

it('returns to the list from Cancel', async () => {
  stubApi(async () => jsonResponse(201, newQuiz))
  await openConfig()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(await screen.findByRole('heading', { name: 'Quizzes' })).toBeTruthy()
})
```


`VideoDetailPage.test.tsx`: add

```tsx
it('renders the quizzes panel in its tab', async () => {
  renderPage(video({}))
  fireEvent.click(await screen.findByRole('tab', { name: 'Quizzes' }))
  expect(await screen.findByRole('heading', { name: 'Quizzes' })).toBeTruthy()
})
```

- [ ] **Step 3: Run, expect FAIL.**

- [ ] **Step 4: `QuizList.tsx`** — same shape as `FlashcardDeckList` (corner-marked `.blueprint qz-quiz` cards, `fc-list`-like header with **New quiz**), using `plural`:

```tsx
<div className="qz-quiz-head">
  <span className="qz-quiz-title">{quiz.title}</span>
  {quiz.attempt_count > 0 && quiz.best_score !== null ? (
    <span className="tabular qz-best">Best {Math.round(quiz.best_score * 100)}%</span>
  ) : (
    <span className="text-muted qz-best-none">Never attempted</span>
  )}
</div>
<span className="text-muted qz-quiz-meta">
  {plural(quiz.question_count, 'question')} · {plural(quiz.attempt_count, 'attempt')}
</span>
<div className="qz-quiz-actions">Take (btn-secondary) · History (btn-secondary) · Delete (btn-ghost form-small, today's confirm)</div>
```

Props `{ videoId, onNew, onTake, onHistory }`; `onDeleted` goes (the panel's take/history views are never open while the list shows). Empty "No quizzes yet.", loading "Loading…", errors `role="alert"` `.form-error`.

- [ ] **Step 5: `QuizConfigForm.tsx`** — like `FlashcardConfigForm`, built from the shared pieces (`name` prefixes `qz-`):

```tsx
const TYPES: { value: QuestionType; label: string; hint: string }[] = [
  { value: 'multiple_choice', label: 'Multiple choice', hint: 'Exactly one correct option' },
  { value: 'multi_select', label: 'Select all that apply', hint: 'All-or-nothing grading' },
  { value: 'true_false', label: 'True / false', hint: 'Always two options' },
]
const OPTION_COUNTS = [
  { value: '3', label: '3' },
  { value: '4', label: '4' },
  { value: '5', label: '5' },
]
```

- `<h3>New quiz</h3>`; `<CountSlider label="Questions" ariaLabel="Number of questions" min={3} max={30} …>`; scope `SegmentedControl name="qz-scope"` + `TopicPicker`.
- Question types (`<div className="form-field"><h6>Question types</h6>…`): one `form-topic` row per type with a checkbox, the ■/□ mark, and `<span className="qz-type-text"><span>{label}</span><span className="text-muted qz-type-hint">{hint}</span></span>`; the checkbox is `disabled` when it is the only checked type; below the rows, when exactly one type is checked, `<p className="text-muted qz-note">At least one type is required.</p>`. Toggling keeps the fixed order: `TYPES.map((t) => t.value).filter((v) => (v === type ? !checked : draft.questionTypes.includes(v)))`.
- Options per question: `SegmentedControl name="qz-options" label="Options per question"` with `OPTION_COUNTS`, value `String(draft.optionsPerQuestion)`, onChange `Number(v)` — rendered only when `draft.questionTypes.some((t) => t !== 'true_false')`.
- Difficulty `SegmentedControl name="qz-difficulty"`; title `.field` (`id="qz-title"`); error; **Generate {count} questions** / **Select at least one topic**; **Cancel** — exactly as the flashcards form.

- [ ] **Step 6: `QuizzesPanel.tsx`** — like `FlashcardsPanel`:

```tsx
const DEFAULT_DRAFT: QuizDraft = {
  count: 6,
  scope: 'whole_video',
  segmentIds: [],
  questionTypes: ['multiple_choice', 'multi_select', 'true_false'],
  optionsPerQuestion: 4,
  difficulty: 'mixed',
  title: '',
}

function toConfig(draft: QuizDraft): QuizConfig {
  const title = draft.title.trim()
  return {
    count: draft.count,
    scope: draft.scope,
    ...(draft.scope === 'topics' ? { segment_ids: draft.segmentIds } : {}),
    question_types: draft.questionTypes,
    ...(draft.questionTypes.some((t) => t !== 'true_false') ? { options_per_question: draft.optionsPerQuestion } : {}),
    difficulty: draft.difficulty,
    ...(title ? { title } : {}),
  }
}

type View = { name: 'list' } | { name: 'config' } | { name: 'take'; quizId: string } | { name: 'history'; quizId: string }
```

`config` renders `<GeneratingStatus heading="Generating quiz…" />` while `createQuiz.isPending`, else the form; success clears `title`/`segmentIds` and goes to `take` of the new quiz; `take` renders today's `<QuizTake key={quizId} videoId quizId onSeek onClose={→ list} />`, `history` today's `<QuizAttemptHistory key={quizId} quizId onSeek onClose={→ list} />`.

- [ ] **Step 7: Page** — the `quizzes` prop becomes `<QuizzesPanel videoId={video.id} segments={video.segments} onSeek={seek} />`; remove `activeQuiz` and the four quiz imports (keep `useState` if still used). `git rm web/src/components/QuizConfigModal.tsx`.

- [ ] **Step 8: CSS** — `Quizzes.css` (list part; take/results in Task 4):

```css
.qz-list { display: flex; flex-direction: column; gap: var(--space-6); }
.qz-list-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.qz-list-head h3 { margin: 0; }
.qz-quiz { display: flex; flex-direction: column; gap: var(--space-2); padding: var(--space-4); }
.qz-quiz-head { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; }
.qz-quiz-title { font-family: var(--font-heading); font-weight: 600; font-size: 18px; overflow-wrap: anywhere; }
.qz-best { font-size: 13px; color: var(--color-accent-700); }
.qz-best-none, .qz-quiz-meta { font-size: 12.5px; }
.qz-quiz-actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.qz-type-text { display: flex; flex-direction: column; }
.qz-type-hint, .qz-note { font-size: 12px; }
.qz-note { margin: 0; }
```

(Write each rule on its own lines, like the rest of the CSS; condensed here.)

- [ ] **Step 9:** `npm test`, `typecheck`, `lint`, `build` — green.
- [ ] **Step 10: Stop for review**, then `git commit -m "feat: move quiz list and config into the tab" -m "Refs #24"`

---

### Task 4: Take, results, history

**Files:** `QuizTake.tsx`, `QuizResults.tsx`, `QuizAttemptHistory.tsx` (rewrite) + tests `QuizTake.test.tsx` (new), `QuizResults.test.tsx` (new), `QuizAttemptHistory.test.tsx` (rewrite), `QuizzesPanel.tsx`, `Quizzes.css`

**Interfaces — produces:**
- `QuizTake({ videoId, quizId, onSubmitted(result: AttemptResult), onClose })` — no results inside.
- `QuizResults({ quiz, result, onSeek })` — the score and question blocks only (no buttons).
- `QuizAttemptHistory({ quizId, onOpen(attemptId), onTakeAgain, onClose })`; `QuizAttemptDetail({ quizId, attemptId, onSeek })` in the same file.
- Panel views gain `{ name: 'take'; quizId; run: number }`, `{ name: 'results'; quizId; result: AttemptResult }`, `{ name: 'attempt'; quizId; attemptId }`.

- [ ] **Step 1: Failing tests**

`web/src/components/QuizTake.test.tsx`:

```tsx
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import type { AttemptResult, Quiz } from '../types/quiz'
import { QuizTake } from './QuizTake'

afterEach(() => {
  vi.unstubAllGlobals()
})

const quiz: Quiz = {
  id: 'q1',
  video_id: 'v1',
  title: 'Loops quiz',
  config: {},
  created_at: '',
  questions: [
    {
      id: 'a',
      order_index: 0,
      question_type: 'multiple_choice',
      prompt: 'Which keyword starts a loop?',
      difficulty: 'easy',
      options: [
        { id: 'a1', text: 'for', order_index: 0 },
        { id: 'a2', text: 'def', order_index: 1 },
        { id: 'a3', text: 'try', order_index: 2 },
      ],
    },
    {
      id: 'b',
      order_index: 1,
      question_type: 'multi_select',
      prompt: 'Which are loops?',
      difficulty: 'medium',
      options: [
        { id: 'b1', text: 'for', order_index: 0 },
        { id: 'b2', text: 'while', order_index: 1 },
        { id: 'b3', text: 'if', order_index: 2 },
      ],
    },
  ],
}

const graded: AttemptResult = { attempt_id: 'x', score: 1, results: [] }

function stubApi() {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) =>
    init?.method === 'POST' ? jsonResponse(201, graded) : jsonResponse(200, quiz),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function posts(fetchMock: ReturnType<typeof stubApi>) {
  return fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')
}

function renderTake(onSubmitted = vi.fn(), onClose = vi.fn()) {
  renderWithClient(<QuizTake videoId="v1" quizId="q1" onSubmitted={onSubmitted} onClose={onClose} />)
  return { onSubmitted, onClose }
}

it('numbers the questions, labels their type, and counts answers', async () => {
  stubApi()
  renderTake()
  expect(await screen.findByText('01')).toBeTruthy()
  expect(screen.getByText('Multiple choice — one answer')).toBeTruthy()
  expect(screen.getByText('Select all that apply')).toBeTruthy()
  expect(screen.getAllByRole('radio')).toHaveLength(3)
  expect(screen.getAllByRole('checkbox')).toHaveLength(3)

  fireEvent.click(screen.getAllByRole('radio', { name: 'for' })[0])
  expect(screen.getByText('1 of 2 answered. Unanswered questions count as incorrect.')).toBeTruthy()
})

it('asks before submitting with unanswered questions, and sends nothing if cancelled', async () => {
  const fetchMock = stubApi()
  const confirm = vi.fn(() => false)
  vi.stubGlobal('confirm', confirm)
  renderTake()
  fireEvent.click(await screen.findByRole('button', { name: 'Submit' }))

  expect(confirm).toHaveBeenCalledWith(
    '2 of 2 questions are unanswered and will count as incorrect. Submit anyway?',
  )
  expect(posts(fetchMock)).toHaveLength(0)
})

it('submits a fully answered quiz without asking, once, and hands up the result', async () => {
  const fetchMock = stubApi()
  const confirm = vi.fn(() => true)
  vi.stubGlobal('confirm', confirm)
  const { onSubmitted } = renderTake()
  fireEvent.click(await screen.findByRole('radio', { name: 'for' }))
  fireEvent.click(screen.getByRole('checkbox', { name: 'while' }))
  const submit = screen.getByRole('button', { name: 'Submit' })
  fireEvent.click(submit)
  fireEvent.click(submit)

  await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith(graded))
  expect(confirm).not.toHaveBeenCalled()
  expect(posts(fetchMock)).toHaveLength(1)
  expect(JSON.parse(String(posts(fetchMock)[0][1]?.body))).toEqual({
    answers: [
      { question_id: 'a', selected_option_ids: ['a1'] },
      { question_id: 'b', selected_option_ids: ['b2'] },
    ],
  })
})

it('asks before closing only when something is selected', async () => {
  stubApi()
  const confirm = vi.fn(() => false)
  vi.stubGlobal('confirm', confirm)
  const { onClose } = renderTake()
  fireEvent.click(await screen.findByRole('button', { name: 'Close' }))
  expect(confirm).not.toHaveBeenCalled()
  expect(onClose).toHaveBeenCalledTimes(1)

  fireEvent.click(screen.getByRole('radio', { name: 'for' }))
  fireEvent.click(screen.getByRole('button', { name: 'Close' }))
  expect(confirm).toHaveBeenCalledWith('Leave this quiz? Your answers so far will be lost.')
  expect(onClose).toHaveBeenCalledTimes(1)
})
```

(The double click relies on the button being disabled while pending — the second `fireEvent.click` on a disabled button is a no-op, and the guard in step 3 covers the instant before the re-render.)

`web/src/components/QuizResults.test.tsx`:

```tsx
import { fireEvent, render, screen, within } from '@testing-library/react'
import { expect, it, vi } from 'vitest'

import type { AttemptResult, Quiz } from '../types/quiz'
import { QuizResults } from './QuizResults'

const quiz: Quiz = {
  id: 'q1',
  video_id: 'v1',
  title: 'Loops quiz',
  config: {},
  created_at: '',
  questions: [
    {
      id: 'b',
      order_index: 0,
      question_type: 'multi_select',
      prompt: 'Which are loops?',
      difficulty: 'medium',
      options: [
        { id: 'b1', text: 'for', order_index: 0 },
        { id: 'b2', text: 'while', order_index: 1 },
        { id: 'b3', text: 'if', order_index: 2 },
        { id: 'b4', text: 'try', order_index: 3 },
      ],
    },
    {
      id: 'c',
      order_index: 1,
      question_type: 'true_false',
      prompt: 'Lists use square brackets.',
      difficulty: 'easy',
      options: [
        { id: 'c1', text: 'True', order_index: 0 },
        { id: 'c2', text: 'False', order_index: 1 },
      ],
    },
  ],
}

const result: AttemptResult = {
  attempt_id: 'x',
  score: 0,
  results: [
    {
      question_id: 'b',
      is_correct: false,
      selected_option_ids: ['b1', 'b3'],
      correct_option_ids: ['b1', 'b2'],
      explanation: 'for and while are loops.',
      segment_id: 's2',
      source_start_time: 298,
    },
    {
      question_id: 'c',
      is_correct: false,
      selected_option_ids: [],
      correct_option_ids: ['c1'],
      explanation: 'Square brackets make a list.',
      segment_id: null,
      source_start_time: null,
    },
  ],
}

it('shows the score and marks every option against your answer', () => {
  const onSeek = vi.fn()
  render(<QuizResults quiz={quiz} result={result} onSeek={onSeek} />)

  expect(screen.getByText('0%')).toBeTruthy()
  expect(screen.getByText('0 of 2 correct · all-or-nothing, no partial credit')).toBeTruthy()
  const options = within(screen.getByRole('list', { name: 'Options for question 1' }))
  expect(options.getByText('for').closest('li')?.textContent).toContain('your answer · correct')
  expect(options.getByText('while').closest('li')?.textContent).toContain('correct answer')
  expect(options.getByText('if').closest('li')?.textContent).toContain('your answer')
  expect(options.getByText('try').closest('li')?.textContent).not.toContain('answer')

  fireEvent.click(screen.getByRole('button', { name: 'Jump to 4:58' }))
  expect(onSeek).toHaveBeenCalledWith(298)
})

it('says when a question was skipped and leaves out Jump without a time', () => {
  render(<QuizResults quiz={quiz} result={result} onSeek={() => {}} />)
  expect(screen.getByText('You skipped this question.')).toBeTruthy()
  expect(screen.getAllByRole('button', { name: /Jump to/ })).toHaveLength(1)
})
```

(`QuizResults` gives each option list `aria-label={`Options for question ${n}`}`.)

`web/src/components/QuizAttemptHistory.test.tsx` (rewrite; keeps the old regression in the detail):

```tsx
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import type { AttemptListItem } from '../types/quiz'
import { QuizAttemptDetail, QuizAttemptHistory } from './QuizAttemptHistory'

afterEach(() => {
  vi.unstubAllGlobals()
})

const attempts: AttemptListItem[] = [
  { id: 'a2', score: 0.75, correct_count: 3, question_count: 4, started_at: new Date().toISOString(), completed_at: new Date().toISOString() },
  { id: 'a1', score: 0.5, correct_count: 2, question_count: 4, started_at: '2026-10-01T12:00:00Z', completed_at: '2026-10-01T12:05:00Z' },
]

it('lists attempts with counts and scores, and opens one', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) =>
    url.endsWith('/attempts') ? jsonResponse(200, attempts) : jsonResponse(200, { id: 'q1', title: 'Loops quiz', questions: [] }),
  ))
  const onOpen = vi.fn()
  const onTakeAgain = vi.fn()
  renderWithClient(<QuizAttemptHistory quizId="q1" onOpen={onOpen} onTakeAgain={onTakeAgain} onClose={() => {}} />)

  expect(await screen.findByText('3 / 4')).toBeTruthy()
  expect(screen.getByText('75%')).toBeTruthy()
  expect(screen.getByText('2 / 4')).toBeTruthy()
  fireEvent.click(screen.getAllByRole('button', { name: /^View attempt from/ })[0])
  expect(onOpen).toHaveBeenCalledWith('a2')
  fireEvent.click(screen.getByRole('button', { name: 'Take it again' }))
  expect(onTakeAgain).toHaveBeenCalled()
})

it('shows the error instead of loading forever when the quiz fetch fails', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) =>
    url.endsWith('/quizzes/q1') ? jsonResponse(500, { detail: 'Quiz lookup failed.' }) : jsonResponse(200, attempts[0]),
  ))
  renderWithClient(<QuizAttemptDetail quizId="q1" attemptId="a1" onSeek={() => {}} />)
  await waitFor(() => expect(screen.getByText('Quiz lookup failed.')).toBeTruthy())
  expect(screen.queryByText('Loading…')).toBeNull()
})
```

Add to `QuizzesPanel.test.tsx`: after taking the new quiz (answer True, Submit with a stubbed `POST /attempts` result), the results show; **Retake** shows the question with **no radio checked**.

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: `QuizTake.tsx`** — rewrite per the spec's Take section:

```tsx
const TYPE_LABEL: Record<QuestionType, string> = {
  multiple_choice: 'Multiple choice — one answer',
  multi_select: 'Select all that apply',
  true_false: 'True / false',
}
```

- `QuestionInputs({ number, question, selected, onChange })`: `<fieldset className="qz-question"><legend className="qz-legend">` with `<span className="tabular qz-ordinal">{String(number).padStart(2, '0')}</span>`, `<span className="qz-prompt">…</span>`, `<span className="text-muted qz-type">{TYPE_LABEL[…]}</span>`; then `<div className="qz-options">` of `<label className={selected ? 'qz-option qz-option-selected' : 'qz-option'}>` with a visible native input (`type` checkbox for `multi_select`, else radio; `name={`qz-${question.id}`}`) and `<span>{option.text}</span>`. Selection logic as today.
- `answered = questions.filter((q) => (selections[q.id] ?? []).length > 0).length`.
- `close()`: `if (answered > 0 && !window.confirm('Leave this quiz? Your answers so far will be lost.')) return; onClose()`.
- `handleSubmit`: `if (submit.isPending) return`; unanswered `k = questions.length - answered`; `if (k > 0 && !window.confirm(`${k} of ${questions.length} questions are unanswered and will count as incorrect. Submit anyway?`)) return`; `try { onSubmitted(await submit.mutateAsync({ answers })) } catch { /* submit.error renders */ }`.
- Layout: `.qz-head` (title `<h3>` + **Close** `.btn-ghost`), loading/error/empty, `<form className="qz-form">`, footer `.qz-footer` with the progress line, error, and `<button type="submit" className="btn btn-primary qz-submit" disabled={submit.isPending}>{submit.isPending ? 'Grading…' : 'Submit'}</button>`.

- [ ] **Step 4: `QuizResults.tsx`** — per the spec's Results section (no buttons): score row `.qz-score` (`.qz-score-value` + muted `.qz-score-summary`); per question `<article className={is_correct ? 'qz-result qz-result-correct' : 'qz-result'}>` with `<span className="qz-mark" role="img" aria-label={is_correct ? 'Correct' : 'Incorrect'}>{is_correct ? '✓' : '✕'}</span>`, prompt `.qz-result-prompt`, `<ul className="qz-result-options" aria-label={`Options for question ${i + 1}`}>`, each option:

```tsx
const [mark, note, tone] =
  selected && correct
    ? ['✓', 'your answer · correct', 'qz-tone-correct']
    : correct
      ? ['✓', 'correct answer', 'qz-tone-correct']
      : selected
        ? ['✕', 'your answer', 'qz-tone-wrong']
        : ['·', '', 'qz-tone-muted']
```

rendered as `<li className={`qz-result-option ${tone}`}><span aria-hidden="true">{mark}</span><span className="qz-option-text">{option.text}</span>{note && <span className="qz-option-note">{note}</span>}</li>`; then the skipped line, `.qz-explanation`, and the Jump `.btn-ghost` when `source_start_time !== null`.

- [ ] **Step 5: `QuizAttemptHistory.tsx`** — `QuizAttemptHistory`: `.qz-head` (`{title} — attempts` + Close), a `<table className="table qz-table">` with `<th>Completed</th><th className="qz-num">Correct</th><th className="qz-num">Score</th>`; rows: `<td><button type="button" className="qz-row-open" aria-label={`View attempt from ${when}`} onClick={() => onOpen(a.id)}>{when}</button></td>` (`when = formatRelative(a.completed_at ?? a.started_at)`), `<td className="qz-num text-muted tabular">{c} / {t}</td>`, `<td className={pct >= 70 ? 'qz-num tabular qz-good' : 'qz-num tabular'}>{pct}%</td>`; empty "No attempts yet."; **Take it again** `.btn-primary`. `QuizAttemptDetail` = today's `AttemptDetail` with "Loading…" and `.form-error` alerts, exported.

- [ ] **Step 6: Panel** — views: `take` `{ quizId, run }` rendering `<QuizTake key={`${quizId}-${run}`} … onSubmitted={(result) => setView({ name: 'results', quizId, result })} onClose={toList} />`; `results` and `attempt` render an internal (non-exported) `QuizResultsScreen` that fetches the quiz with `useQuizQuery`, shows `.qz-head` (title + Close), then `QuizResults` (or `QuizAttemptDetail` for `attempt`), then the footer: results → **Retake** (`take` with `run: Date.now()`) and **Attempt history**; attempt → **← Attempts** and **Take it again**. `history` → `QuizAttemptHistory` with `onOpen`/`onTakeAgain`/`onClose`.

- [ ] **Step 7: CSS** — append to `Quizzes.css` (one property per line in the file):

```css
.qz-take, .qz-history, .qz-results-screen { display: flex; flex-direction: column; gap: var(--space-4); }
.qz-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.qz-head h3 { margin: 0; overflow-wrap: anywhere; }
.qz-form { display: flex; flex-direction: column; gap: var(--space-8); }
.qz-question { margin: 0; padding: 0; border: none; min-width: 0; }
.qz-legend { display: flex; flex-direction: column; gap: var(--space-1); padding: 0; margin-bottom: var(--space-3); }
.qz-ordinal { font-family: var(--font-heading); font-weight: 600; font-size: 14px; color: var(--color-accent-700); }
.qz-prompt { font-family: var(--font-heading); font-weight: 600; font-size: 20px; line-height: 1.18; overflow-wrap: anywhere; }
.qz-type { font-size: 11.5px; letter-spacing: 0.08em; text-transform: uppercase; }
.qz-options { display: flex; flex-direction: column; gap: var(--space-2); padding-left: calc(14px + var(--space-3)); }
.qz-option { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--color-divider); cursor: pointer; overflow-wrap: anywhere; }
.qz-option input { accent-color: var(--color-accent); }
.qz-option-selected { border-color: var(--color-accent); background: var(--color-accent-100); }
.qz-option:has(input:focus-visible) { outline: 2px solid var(--color-accent); outline-offset: 2px; }
.qz-footer { display: flex; flex-direction: column; gap: var(--space-3); padding-top: var(--space-4); border-top: 1px solid var(--color-divider); }
.qz-footer p { margin: 0; font-size: 12.5px; }
.qz-submit { width: 100%; }
.qz-score { display: flex; align-items: baseline; gap: var(--space-4); flex-wrap: wrap; }
.qz-score-value { font-family: var(--font-heading); font-weight: 600; font-size: 52px; line-height: 0.9; }
.qz-score-summary { font-size: 14px; }
.qz-result { display: flex; flex-direction: column; align-items: flex-start; gap: var(--space-2); padding: var(--space-4); border: 1px solid var(--color-divider); background: var(--color-neutral-200); }
.qz-result-correct { border-color: var(--color-accent-300); background: var(--color-accent-100); }
.qz-mark { color: var(--color-text); }
.qz-result-correct .qz-mark { color: var(--color-accent-800); }
.qz-result-prompt { font-family: var(--font-heading); font-weight: 600; font-size: 17px; overflow-wrap: anywhere; }
.qz-result-options { list-style: none; margin: 0; padding: 0; align-self: stretch; }
.qz-result-option { display: flex; gap: var(--space-2); font-size: 13px; padding: 2px 0; }
.qz-option-text { flex: 1; overflow-wrap: anywhere; }
.qz-option-note { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; }
.qz-tone-correct { color: var(--color-accent-800); }
.qz-tone-wrong { color: var(--color-text); }
.qz-tone-muted { color: color-mix(in srgb, var(--color-text) 55%, transparent); }
.qz-skipped, .qz-explanation { margin: 0; font-size: 13px; }
.qz-explanation { line-height: 1.55; color: color-mix(in srgb, var(--color-text) 75%, transparent); }
.qz-num { text-align: right; }
.qz-good { color: var(--color-accent-700); }
.qz-row-open { padding: 0; border: none; background: transparent; color: inherit; font: inherit; text-decoration: underline; text-underline-offset: 3px; cursor: pointer; }
```

- [ ] **Step 8:** `npm test`, `typecheck`, `lint`, `build` — green. A quick browser look at an existing quiz's take and results (no generation).
- [ ] **Step 9: Stop for review**, then `git commit -m "feat: restyle quiz taking, results and history" -m "Refs #24"`

---

### Task 5: Browser check

No commit unless it finds a fix (its own commit and review stop).

- [ ] `docker compose restart web api`. On the Python video, light and dark, 1440×900 and 420px:
  - list: best/never, counts; New quiz → uncheck types down to one (disabled + note; options-per-question hides for true/false only); Selected topics + one topic; Generate 3 questions (one real generation, cents) → "Generating quiz…" → take;
  - take with the keyboard (Tab through options; Space selects); answer all but one → Submit → confirm text → Cancel (nothing sent) → Submit → OK → results;
  - results: score, option notes (a multi-select if generated), skipped line, explanation, Jump seeks + toast;
  - Retake → empty answers; Close with a selection → confirm; Attempt history → table → open an attempt → ← Attempts → Take it again;
  - type answers, switch to Chat and back → still selected;
  - Delete with the confirm cancelled.
- [ ] Clean `.playwright-mcp/` afterwards.
