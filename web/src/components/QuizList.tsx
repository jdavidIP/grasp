import { useDeleteQuiz, useQuizzesQuery } from '../hooks/useQuizzes'

interface QuizListProps {
  videoId: string
  onTake: (quizId: string) => void
  onHistory: (quizId: string) => void
  onDeleted: (quizId: string) => void
}

export function QuizList({ videoId, onTake, onHistory, onDeleted }: QuizListProps) {
  const { data: quizzes, isLoading } = useQuizzesQuery(videoId)
  const deleteQuiz = useDeleteQuiz(videoId)

  if (isLoading) return <p>Loading quizzes...</p>
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
            onClick={() => deleteQuiz.mutate(quiz.id, { onSuccess: () => onDeleted(quiz.id) })}
            disabled={deleteQuiz.isPending}
          >
            Delete
          </button>
        </li>
      ))}
    </ul>
  )
}
