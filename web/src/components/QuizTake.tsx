import { useRef, useState } from 'react'
import { useQuizQuery, useSubmitAttempt } from '../hooks/useQuizzes'
import type { AttemptResult, QuestionType, QuizQuestion } from '../types/quiz'
import './Forms.css'
import './Quizzes.css'

const TYPE_LABEL: Record<QuestionType, string> = {
  multiple_choice: 'Multiple choice — one answer',
  multi_select: 'Select all that apply',
  true_false: 'True / false',
}

interface QuestionInputsProps {
  number: number
  question: QuizQuestion
  selected: string[]
  onChange: (optionIds: string[]) => void
}

function QuestionInputs({ number, question, selected, onChange }: QuestionInputsProps) {
  const multi = question.question_type === 'multi_select'
  return (
    <fieldset className="qz-question">
      <legend className="qz-legend">
        <span className="tabular qz-ordinal">{String(number).padStart(2, '0')}</span>
        <span className="qz-prompt">{question.prompt}</span>
        <span className="text-muted qz-type">{TYPE_LABEL[question.question_type]}</span>
      </legend>
      <div className="qz-options">
        {question.options.map((option) => {
          const checked = selected.includes(option.id)
          return (
            <label key={option.id} className={checked ? 'qz-option qz-option-selected' : 'qz-option'}>
              <input
                type={multi ? 'checkbox' : 'radio'}
                name={`qz-${question.id}`}
                checked={checked}
                onChange={() =>
                  onChange(
                    multi
                      ? checked
                        ? selected.filter((id) => id !== option.id)
                        : [...selected, option.id]
                      : [option.id],
                  )
                }
              />
              <span>{option.text}</span>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}

interface QuizTakeProps {
  videoId: string
  quizId: string
  onSubmitted: (result: AttemptResult) => void
  onClose: () => void
}

// The quiz comes from GET /quizzes/{id}, which withholds the answer key; nothing here
// sees `is_correct` or `explanation` until the graded result comes back.
export function QuizTake({ videoId, quizId, onSubmitted, onClose }: QuizTakeProps) {
  const { data: quiz, isLoading, error } = useQuizQuery(quizId)
  const submit = useSubmitAttempt(videoId, quizId)
  const [selections, setSelections] = useState<Record<string, string[]>>({})
  // A second click can land before `submit.isPending` re-renders; a ref is set at once.
  const submitting = useRef(false)
  const questions = quiz?.questions ?? []
  const answered = questions.filter((q) => (selections[q.id] ?? []).length > 0).length

  function close() {
    // The attempt is already being saved; leaving now would land on its results anyway.
    if (submitting.current) return
    if (answered > 0 && !window.confirm('Leave this quiz? Your answers so far will be lost.')) return
    onClose()
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (submitting.current) return
    const unanswered = questions.length - answered
    if (
      unanswered > 0 &&
      !window.confirm(
        `${unanswered} of ${questions.length} questions are unanswered and will count as incorrect. Submit anyway?`,
      )
    ) {
      return
    }
    submitting.current = true
    try {
      const result = await submit.mutateAsync({
        answers: questions.map((question) => ({
          question_id: question.id,
          selected_option_ids: selections[question.id] ?? [],
        })),
      })
      onSubmitted(result)
    } catch {
      // submit.error renders above the button; the answers stay for a retry.
    } finally {
      submitting.current = false
    }
  }

  return (
    <section className="qz-take">
      <div className="qz-head">
        <h3>{quiz?.title ?? 'Quiz'}</h3>
        <button type="button" className="btn btn-ghost" onClick={close} disabled={submit.isPending}>
          Close
        </button>
      </div>
      {isLoading && <p className="text-muted">Loading…</p>}
      {error && (
        <p role="alert" className="form-error">
          {error.message}
        </p>
      )}
      {quiz && questions.length === 0 && <p className="text-muted">This quiz has no questions.</p>}
      {questions.length > 0 && (
        <form className="qz-form" onSubmit={handleSubmit}>
          {questions.map((question, i) => (
            <QuestionInputs
              key={question.id}
              number={i + 1}
              question={question}
              selected={selections[question.id] ?? []}
              onChange={(optionIds) => setSelections((prev) => ({ ...prev, [question.id]: optionIds }))}
            />
          ))}
          <div className="qz-footer">
            <p className="text-muted">
              {answered} of {questions.length} answered. Unanswered questions count as incorrect.
            </p>
            {submit.error && (
              <p role="alert" className="form-error">
                {submit.error.message}
              </p>
            )}
            <button type="submit" className="btn btn-primary qz-submit" disabled={submit.isPending}>
              {submit.isPending ? 'Grading…' : 'Submit'}
            </button>
          </div>
        </form>
      )}
    </section>
  )
}
