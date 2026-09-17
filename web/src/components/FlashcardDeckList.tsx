import { useDeleteFlashcardDeck, useFlashcardDecksQuery } from '../hooks/useFlashcards'

interface FlashcardDeckListProps {
  videoId: string
  onReview: (deckId: string) => void
  onDeleted: (deckId: string) => void
}

export function FlashcardDeckList({ videoId, onReview, onDeleted }: FlashcardDeckListProps) {
  const { data: decks, isLoading } = useFlashcardDecksQuery(videoId)
  const deleteDeck = useDeleteFlashcardDeck(videoId)

  if (isLoading) return <p>Loading decks...</p>
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
            onClick={() => deleteDeck.mutate(deck.id, { onSuccess: () => onDeleted(deck.id) })}
            disabled={deleteDeck.isPending}
          >
            Delete
          </button>
        </li>
      ))}
    </ul>
  )
}
