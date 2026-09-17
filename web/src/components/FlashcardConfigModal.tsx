import { useRef, useState } from 'react'
import { useCreateFlashcardDeck } from '../hooks/useFlashcards'
import type { FlashcardConfig, FlashcardDifficulty, FlashcardScope, FlashcardStyle } from '../types/flashcard'
import type { Segment } from '../types/video'

const COUNT_OPTIONS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]

interface FlashcardConfigModalProps {
  videoId: string
  segments: Segment[]
  onCreated: (deckId: string) => void
}

export function FlashcardConfigModal({ videoId, segments, onCreated }: FlashcardConfigModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const createDeck = useCreateFlashcardDeck(videoId)
  const [count, setCount] = useState(15)
  const [scope, setScope] = useState<FlashcardScope>('whole_video')
  const [segmentIds, setSegmentIds] = useState<string[]>([])
  const [difficulty, setDifficulty] = useState<FlashcardDifficulty>('mixed')
  const [style, setStyle] = useState<FlashcardStyle>('mixed')
  const [title, setTitle] = useState('')

  function toggleSegment(id: string) {
    setSegmentIds((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]))
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const config: FlashcardConfig = {
      count,
      scope,
      difficulty,
      style,
      ...(scope === 'topics' ? { segment_ids: segmentIds } : {}),
      ...(title.trim() ? { title: title.trim() } : {}),
    }
    const deck = await createDeck.mutateAsync(config)
    dialogRef.current?.close()
    setTitle('')
    setSegmentIds([])
    onCreated(deck.id)
  }

  return (
    <>
      <button type="button" onClick={() => dialogRef.current?.showModal()}>
        New deck
      </button>
      <dialog ref={dialogRef}>
        <form onSubmit={handleSubmit}>
          <h3>Configure flashcard deck</h3>

          <label>
            Count
            <select value={count} onChange={(event) => setCount(Number(event.target.value))}>
              {COUNT_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <fieldset>
            <legend>Scope</legend>
            <label>
              <input
                type="radio"
                name="scope"
                checked={scope === 'whole_video'}
                onChange={() => setScope('whole_video')}
              />
              Whole video
            </label>
            <label>
              <input
                type="radio"
                name="scope"
                checked={scope === 'topics'}
                onChange={() => setScope('topics')}
              />
              Selected topics
            </label>
          </fieldset>

          {scope === 'topics' && (
            <fieldset>
              <legend>Topics</legend>
              {segments.length === 0 && <p>No topics available.</p>}
              {segments.map((segment) => (
                <label key={segment.id}>
                  <input
                    type="checkbox"
                    checked={segmentIds.includes(segment.id)}
                    onChange={() => toggleSegment(segment.id)}
                  />
                  {segment.label}
                </label>
              ))}
            </fieldset>
          )}

          <label>
            Difficulty
            <select
              value={difficulty}
              onChange={(event) => setDifficulty(event.target.value as FlashcardDifficulty)}
            >
              <option value="mixed">Mixed</option>
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </label>

          <label>
            Style
            <select value={style} onChange={(event) => setStyle(event.target.value as FlashcardStyle)}>
              <option value="mixed">Mixed</option>
              <option value="definition">Definition</option>
              <option value="concept">Concept</option>
              <option value="detail">Detail</option>
            </select>
          </label>

          <label>
            Title (optional)
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>

          {createDeck.error && <p role="alert">{createDeck.error.message}</p>}

          <div>
            <button type="button" onClick={() => dialogRef.current?.close()}>
              Cancel
            </button>
            <button
              type="submit"
              disabled={createDeck.isPending || (scope === 'topics' && segmentIds.length === 0)}
            >
              {createDeck.isPending ? 'Generating...' : 'Generate deck'}
            </button>
          </div>
        </form>
      </dialog>
    </>
  )
}
