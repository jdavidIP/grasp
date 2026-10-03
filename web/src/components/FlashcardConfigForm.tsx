import type { FlashcardDifficulty, FlashcardDraft, FlashcardScope, FlashcardStyle } from '../types/flashcard'
import type { Segment } from '../types/video'
import { CountSlider } from './CountSlider'
import { SegmentedControl } from './SegmentedControl'
import { TopicPicker } from './TopicPicker'

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
      className="form"
      onSubmit={(event) => {
        event.preventDefault()
        if (!needsTopic) onSubmit()
      }}
    >
      <h3>New deck</h3>

      <CountSlider
        label="Cards"
        ariaLabel="Number of cards"
        min={5}
        max={50}
        value={draft.count}
        onChange={(n) => set('count', n)}
      />

      <SegmentedControl
        name="fc-scope"
        label="Scope"
        value={draft.scope}
        options={SCOPES}
        onChange={(v) => set('scope', v)}
      />

      {draft.scope === 'topics' && (
        <TopicPicker segments={segments} selectedIds={draft.segmentIds} onToggle={toggleSegment} />
      )}

      <SegmentedControl
        name="fc-difficulty"
        label="Difficulty"
        value={draft.difficulty}
        options={DIFFICULTIES}
        onChange={(v) => set('difficulty', v)}
      />
      <SegmentedControl
        name="fc-style"
        label="Style"
        value={draft.style}
        options={STYLES}
        onChange={(v) => set('style', v)}
      />

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
        <p role="alert" className="form-error">
          {error}
        </p>
      )}

      <div className="form-actions">
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
