import { useQuizQuery } from '../hooks/useQuizzes'
import { formatTime } from '../lib/time'
import type { AttemptResult, Quiz } from '../types/quiz'
import './Forms.css'
import './Quizzes.css'

interface QuizResultsProps {
  quiz: Quiz
  result: AttemptResult
  onSeek: (seconds: number) => void
}

// Renders a graded attempt: a fresh submit or one opened from the history.
export function QuizResults({ quiz, result, onSeek }: QuizResultsProps) {
  const resultByQuestion = new Map(result.results.map((r) => [r.question_id, r]))
  const correctCount = result.results.filter((r) => r.is_correct).length

  return (
    <div className="qz-results">
      <div className="qz-score">
        <span className="tabular qz-score-value">{Math.round(result.score * 100)}%</span>
        <span className="text-muted qz-score-summary">
          {correctCount} of {quiz.questions.length} correct · all-or-nothing, no partial credit
        </span>
      </div>
      {quiz.questions.map((question, i) => {
        const questionResult = resultByQuestion.get(question.id)
        if (!questionResult) return null
        const { is_correct: isCorrect, source_start_time: start } = questionResult
        return (
          <article key={question.id} className={isCorrect ? 'qz-result qz-result-correct' : 'qz-result'}>
            <div className="qz-result-head">
              <span className="qz-mark" role="img" aria-label={isCorrect ? 'Correct' : 'Incorrect'}>
                {isCorrect ? '✓' : '✕'}
              </span>
              <span className="qz-result-prompt">{question.prompt}</span>
            </div>
            <ul className="qz-result-options" aria-label={`Options for question ${i + 1}`}>
              {question.options.map((option) => {
                const selected = questionResult.selected_option_ids.includes(option.id)
                const correct = questionResult.correct_option_ids.includes(option.id)
                const [mark, note, tone] =
                  selected && correct
                    ? ['✓', 'your answer · correct', 'qz-tone-correct']
                    : correct
                      ? ['✓', 'correct answer', 'qz-tone-correct']
                      : selected
                        ? ['✕', 'your answer', 'qz-tone-wrong']
                        : ['·', '', 'qz-tone-muted']
                return (
                  <li key={option.id} className={`qz-result-option ${tone}`}>
                    <span aria-hidden="true">{mark}</span>
                    <span className="qz-option-text">{option.text}</span>
                    {note && <span className="qz-option-note">{note}</span>}
                  </li>
                )
              })}
            </ul>
            {questionResult.selected_option_ids.length === 0 && (
              <p className="text-muted qz-skipped">You skipped this question.</p>
            )}
            <p className="qz-explanation">{questionResult.explanation}</p>
            {start !== null && (
              <button type="button" className="btn btn-ghost" onClick={() => onSeek(start)}>
                Jump to {formatTime(start)}
              </button>
            )}
          </article>
        )
      })}
    </div>
  )
}

interface QuizResultsForProps {
  quizId: string
  result: AttemptResult
  onSeek: (seconds: number) => void
}

// A fresh submit's result, with the quiz (prompts, options) fetched by id.
export function QuizResultsFor({ quizId, result, onSeek }: QuizResultsForProps) {
  const { data: quiz, isLoading, error } = useQuizQuery(quizId)
  if (error) {
    return (
      <p role="alert" className="form-error">
        {error.message}
      </p>
    )
  }
  if (isLoading || !quiz) return <p className="text-muted">Loading…</p>
  return <QuizResults quiz={quiz} result={result} onSeek={onSeek} />
}
