import { API_URL, handleResponse } from './client'
import type { FlashcardConfig, FlashcardDeck, FlashcardDeckListItem } from '../types/flashcard'

export function listFlashcardDecks(videoId: string): Promise<FlashcardDeckListItem[]> {
  return fetch(`${API_URL}/videos/${videoId}/flashcard-decks`).then((res) => handleResponse(res))
}

export function createFlashcardDeck(
  videoId: string,
  config: FlashcardConfig,
): Promise<FlashcardDeck> {
  return fetch(`${API_URL}/videos/${videoId}/flashcard-decks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  }).then((res) => handleResponse(res))
}

export function getFlashcardDeck(deckId: string): Promise<FlashcardDeck> {
  return fetch(`${API_URL}/flashcard-decks/${deckId}`).then((res) => handleResponse(res))
}

export function deleteFlashcardDeck(deckId: string): Promise<void> {
  return fetch(`${API_URL}/flashcard-decks/${deckId}`, { method: 'DELETE' }).then((res) =>
    handleResponse(res),
  )
}
