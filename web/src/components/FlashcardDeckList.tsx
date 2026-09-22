import { useDeleteFlashcardDeck, useFlashcardDecksQuery } from '../hooks/useFlashcards'

interface FlashcardDeckListProps {
  videoId: string
  onReview: (deckId: string) => void
  onDeleted: (deckId: string) => void
}

export function FlashcardDeckList({ videoId, onReview, onDeleted }: FlashcardDeckListProps) {
  const { data: decks, isLoading, error } = useFlashcardDecksQuery(videoId)
  const deleteDeck = useDeleteFlashcardDeck(videoId)

  function handleDelete(deckId: string, title: string) {
    if (!window.confirm(`Delete the deck "${title}"? This cannot be undone.`)) return
    deleteDeck.mutate(deckId, { onSuccess: () => onDeleted(deckId) })
  }

  if (isLoading) return <p>Loading decks...</p>
  if (error) return <p role="alert">{error.message}</p>
  if (!decks || decks.length === 0) return <p>No flashcard decks yet.</p>

  return (
    <ul>
      {decks.map((deck) => (
        <li key={deck.id}>
          <strong>{deck.title}</strong> ({deck.card_count} cards)
          <button type="button" onClick={() => onReview(deck.id)}>
            Review
          </button>
          <button
            type="button"
            onClick={() => handleDelete(deck.id, deck.title)}
            disabled={deleteDeck.isPending}
          >
            Delete
          </button>
          {deleteDeck.isError && deleteDeck.variables === deck.id && (
            <p role="alert">{deleteDeck.error.message}</p>
          )}
        </li>
      ))}
    </ul>
  )
}
