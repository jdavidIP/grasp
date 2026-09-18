import { useState } from 'react'
import { useQuizQuery, useSubmitAttempt } from '../hooks/useQuizzes'
import type { AttemptResult, QuizQuestion } from '../types/quiz'
import { QuizResults } from './QuizResults'

interface QuizTakeProps {
  videoId: string
  quizId: string
  onSeek: (seconds: number) => void
  onClose: () => void
}

function QuestionInputs({
  question,
  selected,
  onChange,
}: {
  question: QuizQuestion
  selected: string[]
  onChange: (optionIds: string[]) => void
}) {
  const multi = question.question_type === 'multi_select'
  return (
    <fieldset>
      <legend>{question.prompt}</legend>
      {question.options.map((option) => (
        <label key={option.id}>
          <input
            type={multi ? 'checkbox' : 'radio'}
            name={question.id}
            checked={selected.includes(option.id)}
            onChange={() =>
              onChange(
                multi
                  ? selected.includes(option.id)
                    ? selected.filter((id) => id !== option.id)
                    : [...selected, option.id]
                  : [option.id],
              )
            }
          />
          {option.text}
        </label>
      ))}
    </fieldset>
  )
}

// Parent must render this with `key={quizId}` so switching quizzes remounts it with
// fresh answers, instead of syncing them via an effect.
export function QuizTake({ videoId, quizId, onSeek, onClose }: QuizTakeProps) {
  const { data: quiz, isLoading } = useQuizQuery(quizId)
  const submit = useSubmitAttempt(videoId, quizId)
  const [selections, setSelections] = useState<Record<string, string[]>>({})
  const [result, setResult] = useState<AttemptResult | null>(null)

  if (isLoading) return <p>Loading quiz...</p>
  if (!quiz) return null
  if (quiz.questions.length === 0) return <p>This quiz has no questions.</p>

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!quiz) return
    const attempt = await submit.mutateAsync({
      answers: quiz.questions.map((question) => ({
        question_id: question.id,
        selected_option_ids: selections[question.id] ?? [],
      })),
    })
    setResult(attempt)
  }

  function retake() {
    setSelections({})
    setResult(null)
  }

  return (
    <section>
      <h3>{quiz.title}</h3>

      {result ? (
        <>
          <QuizResults quiz={quiz} result={result} onSeek={onSeek} />
          <button type="button" onClick={retake}>
            Retake
          </button>
        </>
      ) : (
        <form onSubmit={handleSubmit}>
          {quiz.questions.map((question) => (
            <QuestionInputs
              key={question.id}
              question={question}
              selected={selections[question.id] ?? []}
              onChange={(optionIds) =>
                setSelections((prev) => ({ ...prev, [question.id]: optionIds }))
              }
            />
          ))}
          <p>Unanswered questions count as incorrect.</p>
          {submit.error && <p role="alert">{submit.error.message}</p>}
          <button type="submit" disabled={submit.isPending}>
            {submit.isPending ? 'Grading...' : 'Submit'}
          </button>
        </form>
      )}

      <button type="button" onClick={onClose}>
        Close
      </button>
    </section>
  )
}
