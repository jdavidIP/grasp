import { useState } from 'react'
import { useAttemptQuery, useAttemptsQuery, useQuizQuery } from '../hooks/useQuizzes'
import { QuizResults } from './QuizResults'

interface QuizAttemptHistoryProps {
  quizId: string
  onSeek: (seconds: number) => void
  onClose: () => void
}

function AttemptDetail({
  quizId,
  attemptId,
  onSeek,
}: {
  quizId: string
  attemptId: string
  onSeek: (seconds: number) => void
}) {
  const { data: quiz } = useQuizQuery(quizId)
  const { data: attempt, isLoading } = useAttemptQuery(quizId, attemptId)

  if (isLoading || !quiz) return <p>Loading attempt...</p>
  if (!attempt) return null
  return <QuizResults quiz={quiz} result={attempt} onSeek={onSeek} />
}

// Parent must render this with `key={quizId}` so switching quizzes remounts it with
// no attempt selected.
export function QuizAttemptHistory({ quizId, onSeek, onClose }: QuizAttemptHistoryProps) {
  const { data: quiz } = useQuizQuery(quizId)
  const { data: attempts, isLoading } = useAttemptsQuery(quizId)
  const [selectedAttemptId, setSelectedAttemptId] = useState<string | null>(null)

  return (
    <section>
      <h3>{quiz ? `${quiz.title} — attempts` : 'Attempts'}</h3>
      {isLoading && <p>Loading attempts...</p>}
      {attempts && attempts.length === 0 && <p>No attempts yet.</p>}
      {attempts && attempts.length > 0 && (
        <ul>
          {attempts.map((attempt) => (
            <li key={attempt.id}>
              {new Date(attempt.started_at).toLocaleString()} — {Math.round(attempt.score * 100)}%
              ({attempt.correct_count} of {attempt.question_count})
              <button type="button" onClick={() => setSelectedAttemptId(attempt.id)}>
                View
              </button>
            </li>
          ))}
        </ul>
      )}

      {selectedAttemptId && (
        <AttemptDetail quizId={quizId} attemptId={selectedAttemptId} onSeek={onSeek} />
      )}

      <button type="button" onClick={onClose}>
        Close
      </button>
    </section>
  )
}
