import { formatTime } from '../lib/time'
import type { AttemptResult, Quiz } from '../types/quiz'

interface QuizResultsProps {
  quiz: Quiz
  result: AttemptResult
  onSeek: (seconds: number) => void
}

export function QuizResults({ quiz, result, onSeek }: QuizResultsProps) {
  const resultByQuestion = new Map(result.results.map((r) => [r.question_id, r]))
  const correctCount = result.results.filter((r) => r.is_correct).length

  return (
    <section>
      <h4>
        Score: {Math.round(result.score * 100)}% ({correctCount} of {quiz.questions.length}{' '}
        correct)
      </h4>
      <ol>
        {quiz.questions.map((question) => {
          const questionResult = resultByQuestion.get(question.id)
          if (!questionResult) return null
          const { source_start_time: sourceStartTime } = questionResult
          return (
            <li key={question.id}>
              <p>
                <strong>{question.prompt}</strong> —{' '}
                {questionResult.is_correct ? 'Correct' : 'Incorrect'}
              </p>
              <ul>
                {question.options.map((option) => {
                  const selected = questionResult.selected_option_ids.includes(option.id)
                  const correct = questionResult.correct_option_ids.includes(option.id)
                  return (
                    <li key={option.id}>
                      {option.text}
                      {correct && ' (correct answer)'}
                      {selected && ' (your answer)'}
                    </li>
                  )
                })}
              </ul>
              {questionResult.selected_option_ids.length === 0 && <p>You skipped this question.</p>}
              <p>{questionResult.explanation}</p>
              {sourceStartTime !== null && (
                <button type="button" onClick={() => onSeek(sourceStartTime)}>
                  Jump to {formatTime(sourceStartTime)}
                </button>
              )}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
