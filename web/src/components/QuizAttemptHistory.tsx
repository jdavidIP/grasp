import { useAttemptQuery, useAttemptsQuery, useQuizQuery } from '../hooks/useQuizzes'
import { formatRelative } from '../lib/time'
import { QuizResults } from './QuizResults'
import './Forms.css'
import './Quizzes.css'

interface QuizAttemptDetailProps {
  quizId: string
  attemptId: string
  onSeek: (seconds: number) => void
}

// One past attempt, through the same renderer as a fresh submit.
export function QuizAttemptDetail({ quizId, attemptId, onSeek }: QuizAttemptDetailProps) {
  const { data: quiz, isLoading: quizLoading, error: quizError } = useQuizQuery(quizId)
  const { data: attempt, isLoading: attemptLoading, error: attemptError } = useAttemptQuery(
    quizId,
    attemptId,
  )

  // Errors first: a failed quiz fetch must not leave this on "Loading…".
  if (quizError || attemptError) {
    return (
      <p role="alert" className="form-error">
        {(quizError ?? attemptError)?.message}
      </p>
    )
  }
  if (quizLoading || attemptLoading) return <p className="text-muted">Loading…</p>
  if (!quiz || !attempt) return null
  return <QuizResults quiz={quiz} result={attempt} onSeek={onSeek} />
}

interface QuizAttemptHistoryProps {
  quizId: string
  onOpen: (attemptId: string) => void
  onTakeAgain: () => void
  onClose: () => void
}

export function QuizAttemptHistory({ quizId, onOpen, onTakeAgain, onClose }: QuizAttemptHistoryProps) {
  const { data: quiz, error: quizError } = useQuizQuery(quizId)
  const { data: attempts, isLoading, error: attemptsError } = useAttemptsQuery(quizId)

  return (
    <section className="qz-history">
      <div className="qz-head">
        <h3>{quiz ? `${quiz.title} — attempts` : 'Attempts'}</h3>
        <button type="button" className="btn btn-ghost" onClick={onClose}>
          Close
        </button>
      </div>
      {quizError && (
        <p role="alert" className="form-error">
          {quizError.message}
        </p>
      )}
      {isLoading && <p className="text-muted">Loading…</p>}
      {attemptsError && (
        <p role="alert" className="form-error">
          {attemptsError.message}
        </p>
      )}
      {attempts?.length === 0 && <p className="text-muted">No attempts yet.</p>}
      {attempts && attempts.length > 0 && (
        <table className="table qz-table">
          <thead>
            <tr>
              <th>Completed</th>
              <th className="qz-num">Correct</th>
              <th className="qz-num">Score</th>
            </tr>
          </thead>
          <tbody>
            {attempts.map((attempt) => {
              const when = formatRelative(attempt.completed_at ?? attempt.started_at)
              const percent = Math.round(attempt.score * 100)
              return (
                <tr key={attempt.id}>
                  <td>
                    <button
                      type="button"
                      className="qz-row-open"
                      aria-label={`View attempt from ${when}`}
                      onClick={() => onOpen(attempt.id)}
                    >
                      {when}
                    </button>
                  </td>
                  <td className="qz-num text-muted tabular">
                    {attempt.correct_count} / {attempt.question_count}
                  </td>
                  <td className={percent >= 70 ? 'qz-num tabular qz-good' : 'qz-num tabular'}>{percent}%</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
      <div className="form-actions">
        <button type="button" className="btn btn-primary" onClick={onTakeAgain}>
          Take it again
        </button>
      </div>
    </section>
  )
}
