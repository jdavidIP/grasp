import { useEffect, useRef, useState, type RefObject } from 'react'
import { useCreateFlashcardDeck } from '../hooks/useFlashcards'
import type { FlashcardConfig, FlashcardDraft } from '../types/flashcard'
import type { Segment } from '../types/video'
import { FlashcardConfigForm } from './FlashcardConfigForm'
import { FlashcardDeckList } from './FlashcardDeckList'
import { FlashcardReview } from './FlashcardReview'
import { GeneratingStatus } from './GeneratingStatus'

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

interface FlashcardsViewsProps extends FlashcardsPanelProps {
  rootRef: RefObject<HTMLElement | null>
}

// "Generating" is the config view while the create request is pending, so a failure
// lands back on the form with its error and the draft intact.
function FlashcardsViews({ videoId, segments, onSeek, rootRef }: FlashcardsViewsProps) {
  const createDeck = useCreateFlashcardDeck(videoId)
  const [view, setView] = useState<View>({ name: 'list' })
  const [draft, setDraft] = useState<FlashcardDraft>(DEFAULT_DRAFT)

  // The tab panel keeps its scroll offset when the view swaps, so a view could open
  // part-way down. Only the panel is reset, not the page.
  useEffect(() => {
    const panel = rootRef.current?.closest('[role="tabpanel"]')
    if (panel) panel.scrollTop = 0
  }, [view, rootRef])

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
        segments={segments}
        onSeek={onSeek}
        onClose={() => setView({ name: 'list' })}
      />
    )
  }
  if (view.name === 'config') {
    return createDeck.isPending ? (
      <GeneratingStatus heading="Generating deck…" noun="cards" />
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

export function FlashcardsPanel(props: FlashcardsPanelProps) {
  const rootRef = useRef<HTMLDivElement>(null)
  return (
    <div ref={rootRef}>
      <FlashcardsViews {...props} rootRef={rootRef} />
    </div>
  )
}
