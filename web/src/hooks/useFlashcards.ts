import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createFlashcardDeck,
  deleteFlashcardDeck,
  getFlashcardDeck,
  listFlashcardDecks,
} from '../api/flashcards'
import type { FlashcardConfig } from '../types/flashcard'

const decksKey = (videoId: string) => ['flashcard-decks', videoId]
const deckKey = (deckId: string) => ['flashcard-deck', deckId]

export function useFlashcardDecksQuery(videoId: string) {
  return useQuery({
    queryKey: decksKey(videoId),
    queryFn: () => listFlashcardDecks(videoId),
  })
}

export function useFlashcardDeckQuery(deckId: string) {
  return useQuery({
    queryKey: deckKey(deckId),
    queryFn: () => getFlashcardDeck(deckId),
  })
}

export function useCreateFlashcardDeck(videoId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (config: FlashcardConfig) => createFlashcardDeck(videoId, config),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: decksKey(videoId) }),
  })
}

export function useDeleteFlashcardDeck(videoId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (deckId: string) => deleteFlashcardDeck(deckId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: decksKey(videoId) }),
  })
}
