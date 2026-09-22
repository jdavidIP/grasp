import { useDeleteQuiz, useQuizzesQuery } from '../hooks/useQuizzes'

interface QuizListProps {
  videoId: string
  onTake: (quizId: string) => void
  onHistory: (quizId: string) => void
  onDeleted: (quizId: string) => void
}

export function QuizList({ videoId, onTake, onHistory, onDeleted }: QuizListProps) {
  const { data: quizzes, isLoading, error } = useQuizzesQuery(videoId)
  const deleteQuiz = useDeleteQuiz(videoId)

  function handleDelete(quizId: string, title: string) {
    if (!window.confirm(`Delete the quiz "${title}"? This deletes its attempt history too, and cannot be undone.`)) {
      return
    }
    deleteQuiz.mutate(quizId, { onSuccess: () => onDeleted(quizId) })
  }

  if (isLoading) return <p>Loading quizzes...</p>
  if (error) return <p role="alert">{error.message}</p>
  if (!quizzes || quizzes.length === 0) return <p>No quizzes yet.</p>

  return (
    <ul>
      {quizzes.map((quiz) => (
        <li key={quiz.id}>
          <strong>{quiz.title}</strong> ({quiz.question_count} questions
          {quiz.best_score !== null && `, best ${Math.round(quiz.best_score * 100)}%`})
          <button type="button" onClick={() => onTake(quiz.id)}>
            Take
          </button>
          <button type="button" onClick={() => onHistory(quiz.id)}>
            History
          </button>
          <button
            type="button"
            onClick={() => handleDelete(quiz.id, quiz.title)}
            disabled={deleteQuiz.isPending}
          >
            Delete
          </button>
          {deleteQuiz.isError && deleteQuiz.variables === quiz.id && (
            <p role="alert">{deleteQuiz.error.message}</p>
          )}
        </li>
      ))}
    </ul>
  )
}
