import { useRef, useState } from 'react'
import { useCreateQuiz } from '../hooks/useQuizzes'
import type { QuestionType, QuizConfig, QuizDifficulty, QuizScope } from '../types/quiz'
import type { Segment } from '../types/video'

const COUNT_OPTIONS = [3, 5, 10, 15, 20, 25, 30]
const QUESTION_TYPES: { value: QuestionType; label: string }[] = [
  { value: 'multiple_choice', label: 'Multiple choice (one answer)' },
  { value: 'multi_select', label: 'Multi-select (select all that apply)' },
  { value: 'true_false', label: 'True / false' },
]

interface QuizConfigModalProps {
  videoId: string
  segments: Segment[]
  onCreated: (quizId: string) => void
}

export function QuizConfigModal({ videoId, segments, onCreated }: QuizConfigModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const createQuiz = useCreateQuiz(videoId)
  const [count, setCount] = useState(10)
  const [scope, setScope] = useState<QuizScope>('whole_video')
  const [segmentIds, setSegmentIds] = useState<string[]>([])
  const [questionTypes, setQuestionTypes] = useState<QuestionType[]>(['multiple_choice'])
  const [optionsPerQuestion, setOptionsPerQuestion] = useState(4)
  const [difficulty, setDifficulty] = useState<QuizDifficulty>('mixed')
  const [title, setTitle] = useState('')

  // true/false always has two options, so the option count only matters for the others.
  const usesOptionCount = questionTypes.some((type) => type !== 'true_false')

  function toggleSegment(id: string) {
    setSegmentIds((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]))
  }

  function toggleQuestionType(type: QuestionType) {
    setQuestionTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type],
    )
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const config: QuizConfig = {
      count,
      scope,
      question_types: questionTypes,
      options_per_question: optionsPerQuestion,
      difficulty,
      ...(scope === 'topics' ? { segment_ids: segmentIds } : {}),
      ...(title.trim() ? { title: title.trim() } : {}),
    }
    const quiz = await createQuiz.mutateAsync(config)
    dialogRef.current?.close()
    setTitle('')
    setSegmentIds([])
    onCreated(quiz.id)
  }

  return (
    <>
      <button type="button" onClick={() => dialogRef.current?.showModal()}>
        New quiz
      </button>
      <dialog ref={dialogRef}>
        <form onSubmit={handleSubmit}>
          <h3>Configure quiz</h3>

          <label>
            Questions
            <select value={count} onChange={(event) => setCount(Number(event.target.value))}>
              {COUNT_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <fieldset>
            <legend>Question types</legend>
            {QUESTION_TYPES.map(({ value, label }) => (
              <label key={value}>
                <input
                  type="checkbox"
                  checked={questionTypes.includes(value)}
                  onChange={() => toggleQuestionType(value)}
                />
                {label}
              </label>
            ))}
          </fieldset>

          {usesOptionCount && (
            <label>
              Options per question
              <select
                value={optionsPerQuestion}
                onChange={(event) => setOptionsPerQuestion(Number(event.target.value))}
              >
                {[3, 4, 5].map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
          )}

          <fieldset>
            <legend>Scope</legend>
            <label>
              <input
                type="radio"
                name="quiz-scope"
                checked={scope === 'whole_video'}
                onChange={() => setScope('whole_video')}
              />
              Whole video
            </label>
            <label>
              <input
                type="radio"
                name="quiz-scope"
                checked={scope === 'topics'}
                onChange={() => setScope('topics')}
              />
              Selected topics
            </label>
          </fieldset>

          {scope === 'topics' && (
            <fieldset>
              <legend>Topics</legend>
              {segments.length === 0 && <p>No topics available.</p>}
              {segments.map((segment) => (
                <label key={segment.id}>
                  <input
                    type="checkbox"
                    checked={segmentIds.includes(segment.id)}
                    onChange={() => toggleSegment(segment.id)}
                  />
                  {segment.label}
                </label>
              ))}
            </fieldset>
          )}

          <label>
            Difficulty
            <select
              value={difficulty}
              onChange={(event) => setDifficulty(event.target.value as QuizDifficulty)}
            >
              <option value="mixed">Mixed</option>
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </label>

          <label>
            Title (optional)
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>

          {createQuiz.error && <p role="alert">{createQuiz.error.message}</p>}

          <div>
            <button type="button" onClick={() => dialogRef.current?.close()}>
              Cancel
            </button>
            <button
              type="submit"
              disabled={
                createQuiz.isPending ||
                questionTypes.length === 0 ||
                (scope === 'topics' && segmentIds.length === 0)
              }
            >
              {createQuiz.isPending ? 'Generating...' : 'Generate quiz'}
            </button>
          </div>
        </form>
      </dialog>
    </>
  )
}
