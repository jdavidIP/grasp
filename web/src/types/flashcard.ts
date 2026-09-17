export type FlashcardScope = 'whole_video' | 'topics'
export type FlashcardDifficulty = 'easy' | 'medium' | 'hard' | 'mixed'
export type FlashcardStyle = 'definition' | 'concept' | 'detail' | 'mixed'

export interface FlashcardConfig {
  count: number
  scope: FlashcardScope
  segment_ids?: string[]
  difficulty?: FlashcardDifficulty
  style?: FlashcardStyle
  title?: string
}

export interface Flashcard {
  id: string
  front: string
  back: string
  segment_id: string | null
  source_start_time: number | null
  difficulty: string | null
  order_index: number
}

export interface FlashcardDeck {
  id: string
  video_id: string
  title: string
  config: Record<string, unknown>
  created_at: string
  cards: Flashcard[]
}

export interface FlashcardDeckListItem {
  id: string
  video_id: string
  title: string
  config: Record<string, unknown>
  created_at: string
  card_count: number
}
