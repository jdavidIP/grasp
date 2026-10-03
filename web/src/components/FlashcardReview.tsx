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
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => goTo(index - 1)}
              disabled={index === 0}
            >
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
