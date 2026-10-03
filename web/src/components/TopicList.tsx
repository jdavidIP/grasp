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
