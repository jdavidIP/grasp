import { API_URL, handleResponse } from './client'
import type { ChatMessage, ChatResponse } from '../types/chat'

export function getChatHistory(videoId: string): Promise<ChatMessage[]> {
  return fetch(`${API_URL}/videos/${videoId}/chat`).then((res) => handleResponse(res))
}

export function sendChatMessage(videoId: string, message: string): Promise<ChatResponse> {
  return fetch(`${API_URL}/videos/${videoId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  }).then((res) => handleResponse(res))
}

export function clearChatHistory(videoId: string): Promise<void> {
  return fetch(`${API_URL}/videos/${videoId}/chat`, { method: 'DELETE' }).then((res) =>
    handleResponse(res),
  )
}
