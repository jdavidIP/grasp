import type { QuestionType, QuizDifficulty, QuizDraft, QuizScope } from '../types/quiz'
import type { Segment } from '../types/video'
import { CountSlider } from './CountSlider'
import { SegmentedControl } from './SegmentedControl'
import { TopicPicker } from './TopicPicker'
import './Quizzes.css'

const SCOPES: { value: QuizScope; label: string }[] = [
  { value: 'whole_video', label: 'Whole video' },
  { value: 'topics', label: 'Selected topics' },
]
const TYPES: { value: QuestionType; label: string; hint: string }[] = [
  { value: 'multiple_choice', label: 'Multiple choice', hint: 'Exactly one correct option' },
  { value: 'multi_select', label: 'Select all that apply', hint: 'All-or-nothing grading' },
  { value: 'true_false', label: 'True / false', hint: 'Always two options' },
]
const OPTION_COUNTS: { value: string; label: string }[] = [
  { value: '3', label: '3' },
  { value: '4', label: '4' },
  { value: '5', label: '5' },
]
const DIFFICULTIES: { value: QuizDifficulty; label: string }[] = [
  { value: 'easy', label: 'Easy' },
  { value: 'medium', label: 'Medium' },
  { value: 'hard', label: 'Hard' },
  { value: 'mixed', label: 'Mixed' },
]

interface QuizConfigFormProps {
  draft: QuizDraft
  segments: Segment[]
  error: string | null
  onChange: (draft: QuizDraft) => void
  onSubmit: () => void
  onCancel: () => void
}

export function QuizConfigForm({ draft, segments, error, onChange, onSubmit, onCancel }: QuizConfigFormProps) {
  const needsTopic = draft.scope === 'topics' && draft.segmentIds.length === 0
  const hasOptions = draft.questionTypes.some((type) => type !== 'true_false')

  function set<K extends keyof QuizDraft>(key: K, value: QuizDraft[K]) {
    onChange({ ...draft, [key]: value })
  }

  function toggleSegment(id: string) {
    set(
      'segmentIds',
      draft.segmentIds.includes(id) ? draft.segmentIds.filter((s) => s !== id) : [...draft.segmentIds, id],
    )
  }

  // Rebuilt from TYPES so the payload keeps a fixed order.
  function toggleType(type: QuestionType) {
    const checked = draft.questionTypes.includes(type)
    set(
      'questionTypes',
      TYPES.map((t) => t.value).filter((v) => (v === type ? !checked : draft.questionTypes.includes(v))),
    )
  }

  return (
    <form
      className="form"
      onSubmit={(event) => {
        event.preventDefault()
        if (!needsTopic) onSubmit()
      }}
    >
      <h3>New quiz</h3>

      <CountSlider
        label="Questions"
        ariaLabel="Number of questions"
        min={3}
        max={30}
        value={draft.count}
        onChange={(n) => set('count', n)}
      />

      <SegmentedControl
        name="qz-scope"
        label="Scope"
        value={draft.scope}
        options={SCOPES}
        onChange={(v) => set('scope', v)}
      />

      {draft.scope === 'topics' && (
        <TopicPicker segments={segments} selectedIds={draft.segmentIds} onToggle={toggleSegment} />
      )}

      <div className="form-field">
        <h6>Question types</h6>
        <div className="form-topics">
          {TYPES.map((type) => {
            const checked = draft.questionTypes.includes(type.value)
            // The API needs at least one type, so the last checked one is locked.
            const locked = checked && draft.questionTypes.length === 1
            return (
              <label key={type.value} className={checked ? 'form-topic form-topic-checked' : 'form-topic'}>
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={locked}
                  onChange={() => toggleType(type.value)}
                />
                <span aria-hidden="true" className="form-topic-mark">
                  {checked ? '■' : '□'}
                </span>
                <span className="qz-type-text">
                  <span>{type.label}</span>
                  <span className="text-muted qz-type-hint">{type.hint}</span>
                </span>
              </label>
            )
          })}
        </div>
        {draft.questionTypes.length === 1 && (
          <p className="text-muted qz-note">At least one type is required.</p>
        )}
      </div>

      {hasOptions && (
        <SegmentedControl
          name="qz-options"
          label="Options per question"
          value={String(draft.optionsPerQuestion)}
          options={OPTION_COUNTS}
          onChange={(v) => set('optionsPerQuestion', Number(v))}
        />
      )}

      <SegmentedControl
        name="qz-difficulty"
        label="Difficulty"
        value={draft.difficulty}
        options={DIFFICULTIES}
        onChange={(v) => set('difficulty', v)}
      />

      <div className="field">
        <label htmlFor="qz-title">Title (generated if blank)</label>
        <input
          id="qz-title"
          className="input"
          value={draft.title}
          onChange={(event) => set('title', event.target.value)}
        />
      </div>

      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}

      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={needsTopic}>
          {needsTopic ? 'Select at least one topic' : `Generate ${draft.count} questions`}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  )
}
