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
  const { data: quiz, isLoading: quizLoading, error: quizError } = useQuizQuery(quizId)
  const { data: attempt, isLoading: attemptLoading, error: attemptError } = useAttemptQuery(
    quizId,
    attemptId,
  )

  if (quizLoading || attemptLoading) return <p>Loading attempt...</p>
  if (quizError) return <p role="alert">{quizError.message}</p>
  if (attemptError) return <p role="alert">{attemptError.message}</p>
  if (!quiz || !attempt) return null
  return <QuizResults quiz={quiz} result={attempt} onSeek={onSeek} />
}

// Parent must render this with `key={quizId}` so switching quizzes remounts it with
// no attempt selected.
export function QuizAttemptHistory({ quizId, onSeek, onClose }: QuizAttemptHistoryProps) {
  const { data: quiz, error: quizError } = useQuizQuery(quizId)
  const { data: attempts, isLoading, error: attemptsError } = useAttemptsQuery(quizId)
  const [selectedAttemptId, setSelectedAttemptId] = useState<string | null>(null)

  return (
    <section>
      <h3>{quiz ? `${quiz.title} — attempts` : 'Attempts'}</h3>
      {quizError && <p role="alert">{quizError.message}</p>}
      {isLoading && <p>Loading attempts...</p>}
      {attemptsError && <p role="alert">{attemptsError.message}</p>}
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
