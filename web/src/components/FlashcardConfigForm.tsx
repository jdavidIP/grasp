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
