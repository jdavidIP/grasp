import { apiFetch } from './client'
import type { FlashcardConfig, FlashcardDeck, FlashcardDeckListItem } from '../types/flashcard'

export function listFlashcardDecks(videoId: string): Promise<FlashcardDeckListItem[]> {
  return apiFetch(`/videos/${videoId}/flashcard-decks`)
}

export function createFlashcardDeck(
  videoId: string,
  config: FlashcardConfig,
): Promise<FlashcardDeck> {
  return apiFetch(`/videos/${videoId}/flashcard-decks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
}

export function getFlashcardDeck(deckId: string): Promise<FlashcardDeck> {
  return apiFetch(`/flashcard-decks/${deckId}`)
}

export function deleteFlashcardDeck(deckId: string): Promise<void> {
  return apiFetch(`/flashcard-decks/${deckId}`, { method: 'DELETE' })
}
