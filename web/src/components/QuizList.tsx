import { useDeleteQuiz, useQuizzesQuery } from '../hooks/useQuizzes'
import { plural } from '../lib/format'
import { Corners } from './Corners'
import './Forms.css'
import './Quizzes.css'

interface QuizListProps {
  videoId: string
  onNew: () => void
  onTake: (quizId: string) => void
  onHistory: (quizId: string) => void
}

export function QuizList({ videoId, onNew, onTake, onHistory }: QuizListProps) {
  const { data: quizzes, isLoading, error } = useQuizzesQuery(videoId)
  const deleteQuiz = useDeleteQuiz(videoId)

  function handleDelete(quizId: string, title: string) {
    if (!window.confirm(`Delete the quiz "${title}"? This deletes its attempt history too, and cannot be undone.`)) {
      return
    }
    deleteQuiz.mutate(quizId)
  }

  return (
    <section className="qz-list">
      <div className="qz-list-head">
        <h3>Quizzes</h3>
        <button type="button" className="btn btn-primary" onClick={onNew}>
          New quiz
        </button>
      </div>
      {isLoading && <p className="text-muted">Loading…</p>}
      {error && (
        <p role="alert" className="form-error">
          {error.message}
        </p>
      )}
      {quizzes?.length === 0 && <p className="text-muted">No quizzes yet.</p>}
      {quizzes?.map((quiz) => (
        <article key={quiz.id} className="blueprint qz-quiz">
          <Corners />
          <div className="qz-quiz-head">
            <span className="qz-quiz-title">{quiz.title}</span>
            {quiz.attempt_count > 0 && quiz.best_score !== null ? (
              <span className="tabular qz-best">Best {Math.round(quiz.best_score * 100)}%</span>
            ) : (
              <span className="text-muted qz-best-none">Never attempted</span>
            )}
          </div>
          <span className="text-muted qz-quiz-meta">
            {plural(quiz.question_count, 'question')} · {plural(quiz.attempt_count, 'attempt')}
          </span>
          <div className="qz-quiz-actions">
            <button type="button" className="btn btn-secondary" onClick={() => onTake(quiz.id)}>
              Take
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => onHistory(quiz.id)}>
              History
            </button>
            <button
              type="button"
              className="btn btn-ghost form-small"
              onClick={() => handleDelete(quiz.id, quiz.title)}
              disabled={deleteQuiz.isPending}
            >
              Delete
            </button>
          </div>
          {deleteQuiz.isError && deleteQuiz.variables === quiz.id && (
            <p role="alert" className="form-error">
              {deleteQuiz.error.message}
            </p>
          )}
        </article>
      ))}
    </section>
  )
}
