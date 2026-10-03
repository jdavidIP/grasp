import { useState } from 'react'
import { useCreateQuiz } from '../hooks/useQuizzes'
import type { QuizConfig, QuizDraft } from '../types/quiz'
import type { Segment } from '../types/video'
import { GeneratingStatus } from './GeneratingStatus'
import { QuizAttemptHistory } from './QuizAttemptHistory'
import { QuizConfigForm } from './QuizConfigForm'
import { QuizList } from './QuizList'
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
  | { name: 'take'; quizId: string }
  | { name: 'history'; quizId: string }

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
  const toList = () => setView({ name: 'list' })

  function openConfig() {
    createQuiz.reset()
    setView({ name: 'config' })
  }

  async function generate() {
    try {
      const quiz = await createQuiz.mutateAsync(toConfig(draft))
      setDraft((previous) => ({ ...previous, title: '', segmentIds: [] }))
      setView({ name: 'take', quizId: quiz.id })
    } catch {
      // createQuiz.error renders on the form.
    }
  }

  if (view.name === 'take') {
    return <QuizTake key={view.quizId} videoId={videoId} quizId={view.quizId} onSeek={onSeek} onClose={toList} />
  }
  if (view.name === 'history') {
    return <QuizAttemptHistory key={view.quizId} quizId={view.quizId} onSeek={onSeek} onClose={toList} />
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
      onTake={(quizId) => setView({ name: 'take', quizId })}
      onHistory={(quizId) => setView({ name: 'history', quizId })}
    />
  )
}
