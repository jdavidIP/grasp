import { useRef, type KeyboardEvent, type ReactNode } from 'react'
import { useSearchParams } from 'react-router'
import './WorkspaceTabs.css'

export type TabId = 'chat' | 'flashcards' | 'quizzes'

const TABS: { id: TabId; label: string }[] = [
  { id: 'chat', label: 'Chat' },
  { id: 'flashcards', label: 'Flashcards' },
  { id: 'quizzes', label: 'Quizzes' },
]

function isTabId(value: string | null): value is TabId {
  return TABS.some((tab) => tab.id === value)
}

interface WorkspaceTabsProps {
  chat: ReactNode
  flashcards: ReactNode
  quizzes: ReactNode
}

export function WorkspaceTabs({ chat, flashcards, quizzes }: WorkspaceTabsProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const requested = searchParams.get('tab')
  const active: TabId = isTabId(requested) ? requested : 'chat'
  const tabRefs = useRef<Partial<Record<TabId, HTMLButtonElement | null>>>({})
  const panels: Record<TabId, ReactNode> = { chat, flashcards, quizzes }

  function select(id: TabId, moveFocus: boolean) {
    // replace: switching tabs shouldn't fill the Back button's history.
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous)
        next.set('tab', id)
        return next
      },
      { replace: true },
    )
    if (moveFocus) tabRefs.current[id]?.focus()
  }

  function handleKeyDown(event: KeyboardEvent) {
    const index = TABS.findIndex((tab) => tab.id === active)
    const targets: Record<string, number> = {
      ArrowRight: (index + 1) % TABS.length,
      ArrowLeft: (index - 1 + TABS.length) % TABS.length,
      Home: 0,
      End: TABS.length - 1,
    }
    if (!(event.key in targets)) return
    event.preventDefault()
    select(TABS[targets[event.key]].id, true)
  }

  return (
    <div className="blueprint workspace-tabs">
      <i className="corner tl" />
      <i className="corner tr" />
      <i className="corner bl" />
      <i className="corner br" />
      <div role="tablist" aria-label="Study tools" className="workspace-tablist" onKeyDown={handleKeyDown}>
        {TABS.map((tab) => (
          <button
            key={tab.id}
            ref={(element) => {
              tabRefs.current[tab.id] = element
            }}
            id={`workspace-tab-${tab.id}`}
            type="button"
            role="tab"
            aria-selected={active === tab.id}
            aria-controls={`workspace-panel-${tab.id}`}
            tabIndex={active === tab.id ? 0 : -1}
            className="workspace-tab"
            onClick={() => select(tab.id, false)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {/* All panels stay mounted (hidden when inactive) so a half-taken quiz or a typed
          question survives switching tabs. */}
      {TABS.map((tab) => (
        <div
          key={tab.id}
          id={`workspace-panel-${tab.id}`}
          role="tabpanel"
          aria-labelledby={`workspace-tab-${tab.id}`}
          hidden={active !== tab.id}
          className="workspace-panel"
        >
          {panels[tab.id]}
        </div>
      ))}
    </div>
  )
}
