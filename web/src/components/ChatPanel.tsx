import { useEffect, useRef, useState } from 'react'
import { useChatHistoryQuery, useClearChat, useSendChatMessage } from '../hooks/useChat'
import { formatTime } from '../lib/time'
import type { ChatMessage } from '../types/chat'
import './ChatPanel.css'

interface ChatPanelProps {
  videoId: string
  onSeek: (seconds: number) => void
}

function UserMessage({ text }: { text: string }) {
  return (
    <div className="chat-user">
      <span className="text-muted chat-user-label">You</span>
      <p className="chat-question">{text}</p>
    </div>
  )
}

function AssistantMessage({
  message,
  onSeek,
}: {
  message: ChatMessage
  onSeek: (seconds: number) => void
}) {
  // A broad answer's sources are every segment, which the topics list already shows.
  const sources = message.sources.filter((source) => source.chunk_id !== null)
  return (
    <div className="chat-assistant">
      <p className="chat-answer">{message.content}</p>
      {message.grounded === false ? (
        <span className="tag tag-outline">Not covered in this video</span>
      ) : (
        sources.length > 0 && (
          <details className="chat-sources">
            <summary className="text-muted chat-sources-heading">Sources ({sources.length})</summary>
            <ol className="chat-source-list">
              {sources.map((source, i) => (
                <li key={i} className="chat-source">
                  <span className="tabular chat-source-index">{i + 1}.</span>
                  <div className="chat-source-body">
                    <button
                      type="button"
                      className="tabular chat-source-seek"
                      onClick={() => onSeek(source.start_time)}
                    >
                      {source.segment_label} @ {formatTime(source.start_time)}
                    </button>
                    <details className="chat-source-transcript">
                      <summary className="text-muted">Read transcript</summary>
                      <p className="chat-source-text">{source.text}</p>
                    </details>
                  </div>
                </li>
              ))}
            </ol>
          </details>
        )
      )}
    </div>
  )
}

export function ChatPanel({ videoId, onSeek }: ChatPanelProps) {
  const { data: history, isLoading, error: historyError } = useChatHistoryQuery(videoId)
  const sendMessage = useSendChatMessage(videoId)
  const clearChat = useClearChat(videoId)
  const [draft, setDraft] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  // Shown until the refetched history (which includes it) arrives: the mutation
  // stays pending while its onSuccess invalidation runs.
  const pendingQuestion = sendMessage.isPending ? sendMessage.variables : null
  const count = history?.length ?? 0

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [count, pendingQuestion])

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const question = draft.trim()
    if (!question) return
    try {
      await sendMessage.mutateAsync(question)
      setDraft('')
    } catch {
      // Left in the input for the person to retry; sendMessage.error renders below.
    }
  }

  async function handleClear() {
    if (!window.confirm('Clear the chat history for this video? This cannot be undone.')) return
    try {
      await clearChat.mutateAsync()
    } catch {
      // clearChat.error renders below.
    }
  }

  return (
    <section className="chat-panel" aria-label="Chat">
      <div className="chat-scroll">
        {isLoading && <p className="text-muted">Loading…</p>}
        {historyError && (
          <p role="alert" className="chat-error">
            {historyError.message}
          </p>
        )}
        {history?.length === 0 && !pendingQuestion && (
          <p className="text-muted">Ask anything about this video.</p>
        )}
        <div className="chat-thread">
          {history?.map((message) =>
            message.role === 'user' ? (
              <UserMessage key={message.id} text={message.content} />
            ) : (
              <AssistantMessage key={message.id} message={message} onSeek={onSeek} />
            ),
          )}
          {pendingQuestion && <UserMessage text={pendingQuestion} />}
        </div>
        <div aria-live="polite">
          {pendingQuestion && <p className="text-muted chat-pending">Retrieving…</p>}
        </div>
        <div ref={endRef} />
      </div>

      <div className="chat-composer">
        <form className="chat-composer-row" onSubmit={handleSubmit}>
          <input
            className="input chat-input"
            aria-label="Ask about this video"
            placeholder="Ask about this video…"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={sendMessage.isPending}
          />
          <button
            type="submit"
            className="btn btn-primary chat-send"
            disabled={sendMessage.isPending || !draft.trim()}
          >
            Send
          </button>
          <button
            type="button"
            className="btn btn-ghost chat-clear"
            onClick={handleClear}
            disabled={clearChat.isPending || count === 0}
          >
            Clear
          </button>
        </form>
        {sendMessage.isError && (
          <p role="alert" className="chat-error">
            {sendMessage.error.message}
          </p>
        )}
        {clearChat.isError && (
          <p role="alert" className="chat-error">
            {clearChat.error.message}
          </p>
        )}
      </div>
    </section>
  )
}
