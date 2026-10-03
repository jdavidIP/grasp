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
