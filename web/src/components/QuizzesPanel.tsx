import { useRef, useState, type ReactNode } from 'react'
import { useCreateQuiz, useQuizQuery } from '../hooks/useQuizzes'
import type { AttemptResult, QuizConfig, QuizDraft } from '../types/quiz'
import type { Segment } from '../types/video'
import { GeneratingStatus } from './GeneratingStatus'
import { QuizAttemptDetail, QuizAttemptHistory } from './QuizAttemptHistory'
import { QuizConfigForm } from './QuizConfigForm'
import { QuizList } from './QuizList'
import { QuizResultsFor } from './QuizResults'
import { QuizTake } from './QuizTake'

const DEFAULT_DRAFT: QuizDraft = {
  count: 6,
  scope: 'whole_video',
  segmentIds: [],
  questionTypes: ['multiple_choice', 'multi_select', 'true_false'],
  optionsPerQuestion: 4,
  difficulty: 'mixed',
  title: '',
}

function toConfig(draft: QuizDraft): QuizConfig {
  const title = draft.title.trim()
  return {
    count: draft.count,
    scope: draft.scope,
    ...(draft.scope === 'topics' ? { segment_ids: draft.segmentIds } : {}),
    question_types: draft.questionTypes,
    // True/false always has two options; the field only applies to the other types.
    ...(draft.questionTypes.some((t) => t !== 'true_false')
      ? { options_per_question: draft.optionsPerQuestion }
      : {}),
    difficulty: draft.difficulty,
    ...(title ? { title } : {}),
  }
}

type View =
  | { name: 'list' }
  | { name: 'config' }
  // `run` grows on every take, so the take view remounts with no answers.
  | { name: 'take'; quizId: string; run: number }
  | { name: 'results'; quizId: string; result: AttemptResult }
  | { name: 'history'; quizId: string }
  | { name: 'attempt'; quizId: string; attemptId: string }

interface ResultsScreenProps {
  quizId: string
  onClose: () => void
  children: ReactNode
  actions: ReactNode
}

// The title, Close and footer buttons around a graded attempt.
function ResultsScreen({ quizId, onClose, children, actions }: ResultsScreenProps) {
  const { data: quiz } = useQuizQuery(quizId)
  return (
    <section className="qz-results-screen">
      <div className="qz-head">
        <h3>{quiz?.title ?? 'Results'}</h3>
        <button type="button" className="btn btn-ghost" onClick={onClose}>
          Close
        </button>
      </div>
      {children}
      <div className="form-actions">{actions}</div>
    </section>
  )
}

interface QuizzesPanelProps {
  videoId: string
  segments: Segment[]
  onSeek: (seconds: number) => void
}

// "Generating" is the config view while the create request is pending, so a failure
// lands back on the form with its error and the draft intact.
export function QuizzesPanel({ videoId, segments, onSeek }: QuizzesPanelProps) {
  const createQuiz = useCreateQuiz(videoId)
  const [view, setView] = useState<View>({ name: 'list' })
  const [draft, setDraft] = useState<QuizDraft>(DEFAULT_DRAFT)
  const runs = useRef(0)
  const toList = () => setView({ name: 'list' })
  const take = (quizId: string) => setView({ name: 'take', quizId, run: ++runs.current })
  const history = (quizId: string) => setView({ name: 'history', quizId })

  function openConfig() {
    createQuiz.reset()
    setView({ name: 'config' })
  }

  async function generate() {
    try {
      const quiz = await createQuiz.mutateAsync(toConfig(draft))
      setDraft((previous) => ({ ...previous, title: '', segmentIds: [] }))
      take(quiz.id)
    } catch {
      // createQuiz.error renders on the form.
    }
  }

  if (view.name === 'take') {
    const { quizId } = view
    return (
      <QuizTake
        key={`${quizId}-${view.run}`}
        videoId={videoId}
        quizId={quizId}
        onSubmitted={(result) => setView({ name: 'results', quizId, result })}
        onClose={toList}
      />
    )
  }
  if (view.name === 'results') {
    const { quizId, result } = view
    return (
      <ResultsScreen
        quizId={quizId}
        onClose={toList}
        actions={
          <>
            <button type="button" className="btn btn-primary" onClick={() => take(quizId)}>
              Retake
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => history(quizId)}>
              Attempt history
            </button>
          </>
        }
      >
        <QuizResultsFor quizId={quizId} result={result} onSeek={onSeek} />
      </ResultsScreen>
    )
  }
  if (view.name === 'attempt') {
    const { quizId, attemptId } = view
    return (
      <ResultsScreen
        quizId={quizId}
        onClose={toList}
        actions={
          <>
            <button type="button" className="btn btn-secondary" onClick={() => history(quizId)}>
              ← Attempts
            </button>
            <button type="button" className="btn btn-primary" onClick={() => take(quizId)}>
              Take it again
            </button>
          </>
        }
      >
        <QuizAttemptDetail quizId={quizId} attemptId={attemptId} onSeek={onSeek} />
      </ResultsScreen>
    )
  }
  if (view.name === 'history') {
    const { quizId } = view
    return (
      <QuizAttemptHistory
        key={quizId}
        quizId={quizId}
        onOpen={(attemptId) => setView({ name: 'attempt', quizId, attemptId })}
        onTakeAgain={() => take(quizId)}
        onClose={toList}
      />
    )
  }
  if (view.name === 'config') {
    return createQuiz.isPending ? (
      <GeneratingStatus heading="Generating quiz…" noun="questions" />
    ) : (
      <QuizConfigForm
        draft={draft}
        segments={segments}
        error={createQuiz.error?.message ?? null}
        onChange={setDraft}
        onSubmit={generate}
        onCancel={toList}
      />
    )
  }
  return (
    <QuizList
      videoId={videoId}
      onNew={openConfig}
      onTake={take}
      onHistory={history}
    />
  )
}
