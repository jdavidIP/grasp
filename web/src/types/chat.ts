export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  sources: ChatSource[]
  grounded: boolean | null
  slips: ChatSlip[]
}

export interface ChatSource {
  chunk_id: string | null
  segment_label: string
  start_time: number
  end_time: number
  text: string
}

// A known speaker slip the answer relied on: the transcript says `said`, the speaker
// means `meant`.
export interface ChatSlip {
  said: string
  meant: string
}

export interface ChatResponse {
  answer: string
  sources: ChatSource[]
  grounded: boolean
  slips: ChatSlip[]
}
