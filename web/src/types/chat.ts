export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ChatSource {
  chunk_id: string | null
  segment_label: string
  start_time: number
  end_time: number
  text: string
}

export interface ChatResponse {
  answer: string
  sources: ChatSource[]
  grounded: boolean
}
