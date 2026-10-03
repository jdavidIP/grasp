# Quizzes tab — design

Sub-project 5 of 5 for [#24](https://github.com/jdavidIP/grasp/issues/24) (the last; its PR closes #24). Issue-wide decisions: `2026-10-03-ui-foundation-library-design.md`; workspace shell: `2026-10-03-workspace-shell-design.md`; the flashcards tab this mirrors: `2026-10-03-flashcards-tab-design.md`. Visual reference: handoff §6 (`docs/design/README.md`).

## Scope

- The Quizzes tab becomes one panel — **list → config → generating → take → results**, plus **history** and **attempt detail** — replacing `QuizConfigModal`'s `<dialog>`.
- Restyle list, take, results and history to the handoff.
- One small backend addition: `attempt_count` on the quiz list (user decision A).
- Extract the form pieces the flashcards tab introduced so both config forms share them.

Not in scope: per-question timing, partial credit, chunk-level jump times (#50), any change to grading or generation.

## 1. Backend: `attempt_count`

- `QuizListItem` gains `attempt_count: int` — the number of attempts on the quiz, 0 when never attempted.
- Computed in the same grouped query that already yields `best_score` in `GET /videos/{id}/quizzes` (`count(QuizAttempt.id)` next to `max(QuizAttempt.score)`).
- `docs/API.md`: the list response documents `attempt_count`.

## 2. Shared form pieces (extraction, no visible change)

From the flashcards tab into their own files, used by both config forms:

- `SegmentedControl.tsx` — the native-radio `.seg` group (`name`, `label`, `value`, `options`, `onChange`), today's `Seg` in `FlashcardConfigForm`.
- `TopicPicker.tsx` — the "Topics / {n} of {total} selected" header and the ■/□ checkbox rows, with "No topics available." (`segments`, `selectedIds`, `onToggle`).
- `GeneratingStatus.tsx` — today's `FlashcardGenerating` with a `heading` prop ("Generating deck…" / "Generating quiz…"); same status line and elapsed counter.
- Their CSS moves from `Flashcards.css` to a shared `Forms.css` (`.form-*` classes for the moved rules).

The flashcards tests pass unchanged.

## 3. Panel

**`QuizzesPanel`** owns the tab and the config draft (`QuizDraft` in `types/quiz.ts`: count, scope, segmentIds, questionTypes, optionsPerQuestion, difficulty, title). Views:

| View | Shows | Leaves to |
|---|---|---|
| `list` | `QuizList` | New quiz → `config`; Take → `take`; History → `history` |
| `config` | `QuizConfigForm`, or `GeneratingStatus` while the create request is pending | Cancel → `list`; success → `take` of the new quiz; failure (e.g. `422`) → stays, error shown, draft kept |
| `take` | `QuizTake` | Submit → `results` with the response; Close → `list` (confirm if any answer is selected) |
| `results` | `QuizResults` for the submit response | Retake → `take` (fresh answers); Attempt history → `history`; Close → `list` |
| `history` | `QuizAttemptHistory` | a row → `attempt`; Take it again → `take`; Close → `list` |
| `attempt` | `QuizResults` for `GET /quizzes/{id}/attempts/{attempt_id}` | ← Attempts → `history`; Take it again → `take` |

- `take` and `results` are keyed by quiz id (and a retake counter) so a retake starts empty.
- `VideoDetailPage` drops `activeQuiz`; the Quizzes tab renders `<QuizzesPanel videoId segments onSeek />`. `QuizConfigModal.tsx` is deleted.
- Data: the existing hooks in `useQuizzes.ts`, unchanged. The answer key (`is_correct`, `explanation`) is never requested before submit — `GET /quizzes/{id}` withholds it.
- Styles: `Quizzes.css`, `.qz-*`, Industry tokens only; reuses `Corners`.

## 4. Views

### List
- Header `<h3>Quizzes</h3>` + **New quiz** `.btn-primary`.
- One `.blueprint` card per quiz (corner marks), like the deck cards: title (Barlow Condensed 600 18px); right: "Best {round(best_score×100)}%" in `--color-accent-700`, or muted "Never attempted" when `attempt_count` is 0; a muted 12.5px line "{question_count} questions · {attempt_count} attempts" (singulars); **Take** `.btn-secondary`, **History** `.btn-secondary`, **Delete** `.btn-ghost` 12.5px with today's confirm (`Delete the quiz "{title}"? This deletes its attempt history too, and cannot be undone.`).
- Empty "No quizzes yet."; loading/error as flashcards.

### Config (`QuizConfigForm`)
`<h3>New quiz</h3>`, fields mapping to `POST /videos/{id}/quizzes`:

| Field | Control | Values |
|---|---|---|
| `count` | range 3–30, `aria-label="Number of questions"`, live value | default 6 |
| `scope` | `SegmentedControl` | Whole video / Selected topics; `TopicPicker` when topics |
| `question_types` | three checkbox rows (topic-row style), label + muted hint: Multiple choice — "Exactly one correct option"; Select all that apply — "All-or-nothing grading"; True / false — "Always two options" | all checked by default; the last checked one is disabled with a muted note "At least one type is required." |
| `options_per_question` | `SegmentedControl` 3 / 4 / 5 | default 4; hidden when only true/false is checked, and then omitted from the payload |
| `difficulty` | `SegmentedControl` | easy / medium / hard / mixed (default) |
| `title` | `.field` + `.input`, "Title (generated if blank)" | optional |

- **Generate {count} questions** `.btn-primary` / disabled **Select at least one topic**; **Cancel** `.btn-secondary`. Error above the buttons with `role="alert"`.
- Payload: `segment_ids` only for topics; `options_per_question` only when a non-true/false type is checked; `title` only when non-blank (trimmed); `question_types` in the fixed order multiple_choice, multi_select, true_false.

### Generating
`GeneratingStatus heading="Generating quiz…"`.

### Take (`QuizTake`)
- Header: quiz title `<h3>` + **Close** `.btn-ghost`. Close with ≥1 answer selected asks `window.confirm("Leave this quiz? Your answers so far will be lost.")`; with none, it just closes.
- Each question a `<fieldset>` whose `<legend>` holds: the ordinal `01` (Barlow Condensed 600 14px tabular `--color-accent-700`), the prompt (Barlow Condensed 600 20px, `line-height: 1.18`, `overflow-wrap: anywhere`), then a muted 11.5px uppercase type label: "Multiple choice — one answer" / "Select all that apply" / "True / false".
- Options indented `calc(14px + var(--space-3))`, each a `<label>` row with its native input visible (radio; checkbox for `multi_select`), `padding: var(--space-3)`, `border: 1px solid var(--color-divider)`; selected: `--color-accent` border, `--color-accent-100` fill. Focus visible on the row.
- Footer: hairline; muted 12.5px "{n} of {m} answered. Unanswered questions count as incorrect."; full-width **Submit** `.btn-primary` ("Grading…", disabled while pending). With any question unanswered, Submit asks `window.confirm("{k} of {m} questions are unanswered and will count as incorrect. Submit anyway?")` (user decision); cancelled sends nothing. A submit error shows with `role="alert"`, answers kept.
- Loading "Loading…"; a quiz with no questions: "This quiz has no questions."

### Results (`QuizResults`)
- Score: `Math.round(score × 100)%`, Barlow Condensed 600 52px, `line-height: 0.9`, tabular; beside it muted 14px "{correct} of {total} correct · all-or-nothing, no partial credit".
- One block per question, `padding: var(--space-4)`: correct — `border: 1px solid var(--color-accent-300)`, `background: var(--color-accent-100)`; incorrect — `--color-divider` / `--color-neutral-200`.
  - `✓` (`--color-accent-800`) or `✕` (`--color-text`), then the prompt (Barlow Condensed 600 17px).
  - Every option at 13px with a mark and a right-aligned 11px uppercase note: correct + selected → `✓` "your answer · correct"; correct only → `✓` "correct answer"; selected only → `✕` "your answer"; neither → `·` and no note. Correct options `--color-accent-800`, a wrong pick `--color-text`, the rest muted.
  - "You skipped this question." (muted) when nothing was selected.
  - The explanation, 13px, `line-height: 1.55`, `color-mix(in srgb, var(--color-text) 75%, transparent)`.
  - **Jump to {mm:ss}** `.btn-ghost` from `source_start_time`, omitted when null.
- Footer (after taking): **Retake** `.btn-primary`, **Attempt history** `.btn-secondary`. In attempt detail: **← Attempts** `.btn-secondary`, **Take it again** `.btn-primary`. Close at the top in both.

### History (`QuizAttemptHistory`)
- `<h3>{title} — attempts</h3>` + Close.
- A `.table`, newest first: **Completed** (`formatRelative(completed_at ?? started_at)`), **Correct** (right-aligned muted "{correct_count} / {question_count}"), **Score** (right-aligned percent, `--color-accent-700` at ≥ 70%, else `--color-text`). Each row's Completed cell is a button "View attempt from {relative}" opening the attempt (keyboard reachable).
- Empty "No attempts yet."; **Take it again** `.btn-primary` below.

## Files

| File | Change |
|---|---|
| `api/app/schemas/quiz.py`, `api/app/routers/quizzes.py`, `docs/API.md`, `api/tests/test_quizzes.py` | `attempt_count` |
| `web/src/components/SegmentedControl.tsx`, `TopicPicker.tsx`, `GeneratingStatus.tsx`, `Forms.css` (new) | extracted |
| `web/src/components/FlashcardConfigForm.tsx`, `FlashcardsPanel.tsx`, `Flashcards.css`; `FlashcardGenerating.tsx` (deleted) | use the shared pieces |
| `web/src/types/quiz.ts` | `QuizListItem.attempt_count`, `QuizDraft` |
| `web/src/components/QuizzesPanel.tsx`, `QuizConfigForm.tsx` (new); `QuizConfigModal.tsx` (deleted) | panel, form |
| `web/src/components/QuizList.tsx`, `QuizTake.tsx`, `QuizResults.tsx`, `QuizAttemptHistory.tsx` | restyle / restructure |
| `web/src/components/Quizzes.css` (new) | `.qz-*` |
| `web/src/pages/VideoDetailPage.tsx` | Quizzes tab renders the panel |

## Testing

- **pytest:** the quiz list returns `attempt_count` 0 for a new quiz and 2 after two attempts.
- **Vitest + RTL:**
  - List: best score vs "Never attempted"; the meta line with singulars; cancelled Delete sends nothing.
  - Config: the last checked type can't be unchecked; options-per-question hidden for true/false only and omitted from the payload; the exact payload; a `422` keeps the draft.
  - Panel: New quiz → generating → take of the new quiz; Cancel → list.
  - Take: the answered counter; checkboxes for multi-select, radios otherwise; Submit with unanswered asks and a cancel sends nothing; fully answered submits without asking; Close with a selection asks, without one doesn't.
  - Results: score and summary; option notes for a multi-select question (correct-but-missed, wrong pick, correct pick); skipped text; Jump seeks; no Jump without a time.
  - History: rows newest first with counts and scores; a row opens the attempt's results; Take it again.
  - Flashcards suite unchanged after the extraction; `VideoDetailPage` renders the quizzes panel.
- `typecheck`, `lint`, `build`.
- **Browser check** (light/dark, desktop/narrow): generate a real 3-question quiz (cents), take it with mouse and keyboard, submit with one unanswered (cancel, then accept), results + Jump, retake, history + attempt detail, delete with confirm cancelled.
