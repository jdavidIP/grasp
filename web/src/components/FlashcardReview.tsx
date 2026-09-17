import { useState } from 'react'
import { useFlashcardDeckQuery } from '../hooks/useFlashcards'
import { formatTime } from '../lib/time'

interface FlashcardReviewProps {
  deckId: string
  onSeek: (seconds: number) => void
  onClose: () => void
}

// Parent must render this with `key={deckId}` so switching decks remounts it
// with fresh index/revealed state, instead of syncing it via an effect.
export function FlashcardReview({ deckId, onSeek, onClose }: FlashcardReviewProps) {
  const { data: deck, isLoading } = useFlashcardDeckQuery(deckId)
  const [index, setIndex] = useState(0)
  const [revealed, setRevealed] = useState(false)

  if (isLoading) return <p>Loading deck...</p>
  if (!deck) return null
  if (deck.cards.length === 0) return <p>This deck has no cards.</p>

  const card = deck.cards[index]
  const { source_start_time: sourceStartTime } = card

  function goTo(nextIndex: number) {
    setIndex(nextIndex)
    setRevealed(false)
  }

  return (
    <section>
      <h3>{deck.title}</h3>
      <p>
        Card {index + 1} of {deck.cards.length}
      </p>

      <button type="button" onClick={() => setRevealed((r) => !r)}>
        <p>{revealed ? card.back : card.front}</p>
        <span>{revealed ? '(click to hide answer)' : '(click to reveal answer)'}</span>
      </button>

      {sourceStartTime !== null && (
        <button type="button" onClick={() => onSeek(sourceStartTime)}>
          Jump to {formatTime(sourceStartTime)}
        </button>
      )}

      <div>
        <button type="button" onClick={() => goTo(index - 1)} disabled={index === 0}>
          Previous
        </button>
        <button
          type="button"
          onClick={() => goTo(index + 1)}
          disabled={index === deck.cards.length - 1}
        >
          Next
        </button>
      </div>

      <button type="button" onClick={onClose}>
        Close
      </button>
    </section>
  )
}
