import { useState } from 'react'
import { useCreateFlashcardDeck } from '../hooks/useFlashcards'
import type { FlashcardConfig, FlashcardDraft } from '../types/flashcard'
import type { Segment } from '../types/video'
import { FlashcardConfigForm } from './FlashcardConfigForm'
import { FlashcardDeckList } from './FlashcardDeckList'
import { FlashcardGenerating } from './FlashcardGenerating'
import { FlashcardReview } from './FlashcardReview'

const DEFAULT_DRAFT: FlashcardDraft = {
  count: 12,
  scope: 'whole_video',
  segmentIds: [],
  difficulty: 'mixed',
  style: 'mixed',
  title: '',
}

function toConfig(draft: FlashcardDraft): FlashcardConfig {
  const title = draft.title.trim()
  return {
    count: draft.count,
    scope: draft.scope,
    ...(draft.scope === 'topics' ? { segment_ids: draft.segmentIds } : {}),
    difficulty: draft.difficulty,
    style: draft.style,
    ...(title ? { title } : {}),
  }
}

type View = { name: 'list' } | { name: 'config' } | { name: 'review'; deckId: string }

interface FlashcardsPanelProps {
  videoId: string
  segments: Segment[]
  onSeek: (seconds: number) => void
}

// "Generating" is the config view while the create request is pending, so a failure
// lands back on the form with its error and the draft intact.
export function FlashcardsPanel({ videoId, segments, onSeek }: FlashcardsPanelProps) {
  const createDeck = useCreateFlashcardDeck(videoId)
  const [view, setView] = useState<View>({ name: 'list' })
  const [draft, setDraft] = useState<FlashcardDraft>(DEFAULT_DRAFT)

  function openConfig() {
    createDeck.reset()
    setView({ name: 'config' })
  }

  async function generate() {
    try {
      const deck = await createDeck.mutateAsync(toConfig(draft))
      setDraft((previous) => ({ ...previous, title: '', segmentIds: [] }))
      setView({ name: 'review', deckId: deck.id })
    } catch {
      // createDeck.error renders on the form.
    }
  }

  if (view.name === 'review') {
    return (
      <FlashcardReview
        key={view.deckId}
        deckId={view.deckId}
        onSeek={onSeek}
        onClose={() => setView({ name: 'list' })}
      />
    )
  }
  if (view.name === 'config') {
    return createDeck.isPending ? (
      <FlashcardGenerating />
    ) : (
      <FlashcardConfigForm
        draft={draft}
        segments={segments}
        error={createDeck.error?.message ?? null}
        onChange={setDraft}
        onSubmit={generate}
        onCancel={() => setView({ name: 'list' })}
      />
    )
  }
  return (
    <FlashcardDeckList
      videoId={videoId}
      onNew={openConfig}
      onReview={(deckId) => setView({ name: 'review', deckId })}
    />
  )
}
