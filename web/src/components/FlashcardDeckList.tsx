import { useDeleteFlashcardDeck, useFlashcardDecksQuery } from '../hooks/useFlashcards'
import { deckConfigSummary, plural } from '../lib/format'
import { formatRelative } from '../lib/time'
import { Corners } from './Corners'
import './Flashcards.css'

interface FlashcardDeckListProps {
  videoId: string
  onNew: () => void
  onReview: (deckId: string) => void
}

export function FlashcardDeckList({ videoId, onNew, onReview }: FlashcardDeckListProps) {
  const { data: decks, isLoading, error } = useFlashcardDecksQuery(videoId)
  const deleteDeck = useDeleteFlashcardDeck(videoId)

  function handleDelete(deckId: string, title: string) {
    if (!window.confirm(`Delete the deck "${title}"? This cannot be undone.`)) return
    deleteDeck.mutate(deckId)
  }

  return (
    <section className="fc-list">
      <div className="fc-list-head">
        <h3>Flashcard decks</h3>
        <button type="button" className="btn btn-primary" onClick={onNew}>
          New deck
        </button>
      </div>
      {isLoading && <p className="text-muted">Loading…</p>}
      {error && (
        <p role="alert" className="fc-error">
          {error.message}
        </p>
      )}
      {decks?.length === 0 && <p className="text-muted">No flashcard decks yet.</p>}
      {decks?.map((deck) => (
        <article key={deck.id} className="blueprint fc-deck">
          <Corners />
          <div className="fc-deck-head">
            <span className="fc-deck-title">{deck.title}</span>
            <span className="text-muted tabular fc-deck-meta">
              {plural(deck.card_count, 'card')} · {formatRelative(deck.created_at)}
            </span>
          </div>
          <span className="text-muted fc-deck-summary">{deckConfigSummary(deck.config)}</span>
          <div className="fc-deck-actions">
            <button type="button" className="btn btn-secondary" onClick={() => onReview(deck.id)}>
              Review
            </button>
            <button
              type="button"
              className="btn btn-ghost fc-small"
              onClick={() => handleDelete(deck.id, deck.title)}
              disabled={deleteDeck.isPending}
            >
              Delete
            </button>
          </div>
          {deleteDeck.isError && deleteDeck.variables === deck.id && (
            <p role="alert" className="fc-error">
              {deleteDeck.error.message}
            </p>
          )}
        </article>
      ))}
    </section>
  )
}
