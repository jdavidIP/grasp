import { apiFetch } from './client'
import type { ChatMessage, ChatResponse } from '../types/chat'

export function getChatHistory(videoId: string): Promise<ChatMessage[]> {
  return apiFetch(`/videos/${videoId}/chat`)
}

export function sendChatMessage(videoId: string, message: string): Promise<ChatResponse> {
  return apiFetch(`/videos/${videoId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
}

export function clearChatHistory(videoId: string): Promise<void> {
  return apiFetch(`/videos/${videoId}/chat`, { method: 'DELETE' })
}
