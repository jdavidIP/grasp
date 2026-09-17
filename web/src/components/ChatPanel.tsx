import { useState } from 'react'
import { useChatHistoryQuery, useClearChat, useSendChatMessage } from '../hooks/useChat'
import { formatTime } from '../lib/time'
import type { ChatSource } from '../types/chat'

interface ChatPanelProps {
  videoId: string
  onSeek: (seconds: number) => void
}

interface AnswerMeta {
  sources: ChatSource[]
  grounded: boolean
}

export function ChatPanel({ videoId, onSeek }: ChatPanelProps) {
  const { data: history, isLoading } = useChatHistoryQuery(videoId)
  const sendMessage = useSendChatMessage(videoId)
  const clearChat = useClearChat(videoId)
  const [draft, setDraft] = useState('')
  // GET /videos/{id}/chat doesn't return sources (see docs/API.md — only the raw
  // message is persisted), so chips only show for answers sent this session,
  // matched back to their history row by exact answer text.
  const [metaByAnswer, setMetaByAnswer] = useState<Map<string, AnswerMeta>>(new Map())

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const question = draft.trim()
    if (!question) return
    setDraft('')
    const response = await sendMessage.mutateAsync(question)
    setMetaByAnswer((prev) =>
      new Map(prev).set(response.answer, { sources: response.sources, grounded: response.grounded }),
    )
  }

  async function handleClear() {
    await clearChat.mutateAsync()
    setMetaByAnswer(new Map())
  }

  return (
    <section>
      <h2>Chat</h2>
      {isLoading && <p>Loading...</p>}

      <ul>
        {history?.map((message) => {
          const meta = message.role === 'assistant' ? metaByAnswer.get(message.content) : undefined
          return (
            <li key={message.id}>
              <strong>{message.role}:</strong> {message.content}
              {meta && !meta.grounded && <span className="status-failed"> (not covered)</span>}
              {meta && meta.sources.length > 0 && (
                <div>
                  {meta.sources.map((source, j) => (
                    <button key={j} type="button" onClick={() => onSeek(source.start_time)}>
                      {source.segment_label} @ {formatTime(source.start_time)}
                    </button>
                  ))}
                </div>
              )}
            </li>
          )
        })}
      </ul>

      <form onSubmit={handleSubmit}>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask about this video..."
        />
        <button type="submit" disabled={sendMessage.isPending}>
          Send
        </button>
      </form>
      <button type="button" onClick={handleClear} disabled={clearChat.isPending}>
        Clear chat
      </button>
    </section>
  )
}
