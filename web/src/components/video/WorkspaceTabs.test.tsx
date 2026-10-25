import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation, useNavigationType } from 'react-router'
import { expect, it } from 'vitest'

import { WorkspaceTabs } from './WorkspaceTabs'

function LocationProbe() {
  const location = useLocation()
  const navigationType = useNavigationType()
  return <output data-testid="location">{`${navigationType} ${location.search}`}</output>
}

function renderTabs(entry = '/videos/v1') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <WorkspaceTabs
        chat={<input aria-label="Chat draft" />}
        flashcards={<p>Deck list</p>}
        quizzes={<p>Quiz list</p>}
      />
      <LocationProbe />
    </MemoryRouter>,
  )
}

function selectedTab() {
  return screen.getAllByRole('tab').find((tab) => tab.getAttribute('aria-selected') === 'true')
}

it('starts on Chat with linked tab and panel semantics', () => {
  renderTabs()
  expect(screen.getByRole('tablist', { name: 'Study tools' })).toBeTruthy()
  const tabs = screen.getAllByRole('tab')
  expect(tabs.map((tab) => tab.textContent)).toEqual(['Chat', 'Flashcards', 'Quizzes'])
  expect(selectedTab()?.textContent).toBe('Chat')
  expect(tabs.map((tab) => tab.tabIndex)).toEqual([0, -1, -1])

  const panel = screen.getByRole('tabpanel')
  expect(panel.id).toBe(tabs[0].getAttribute('aria-controls'))
  expect(panel.getAttribute('aria-labelledby')).toBe(tabs[0].id)
  const hiddenDecks = screen.getByText('Deck list').closest('[role="tabpanel"]') as HTMLElement
  expect(hiddenDecks.hidden).toBe(true)
})

it('moves selection and focus with the arrow keys, Home and End', () => {
  renderTabs()
  const tablist = screen.getByRole('tablist')

  fireEvent.keyDown(tablist, { key: 'ArrowLeft' })
  expect(selectedTab()?.textContent).toBe('Quizzes')
  expect(document.activeElement).toBe(selectedTab())

  fireEvent.keyDown(tablist, { key: 'ArrowRight' })
  expect(selectedTab()?.textContent).toBe('Chat')

  fireEvent.keyDown(tablist, { key: 'End' })
  expect(selectedTab()?.textContent).toBe('Quizzes')

  fireEvent.keyDown(tablist, { key: 'Home' })
  expect(selectedTab()?.textContent).toBe('Chat')
  expect(document.activeElement).toBe(selectedTab())
})

it('keeps a hidden panel mounted so what you typed survives switching', () => {
  renderTabs()
  fireEvent.change(screen.getByLabelText('Chat draft'), { target: { value: 'What is a loop?' } })

  fireEvent.click(screen.getByRole('tab', { name: 'Flashcards' }))
  expect(screen.getByRole('tabpanel').textContent).toBe('Deck list')
  fireEvent.click(screen.getByRole('tab', { name: 'Chat' }))

  expect(screen.getByLabelText('Chat draft')).toHaveProperty('value', 'What is a loop?')
})

it('opens the tab named in ?tab= and falls back to Chat for an unknown one', () => {
  const { unmount } = renderTabs('/videos/v1?tab=quizzes')
  expect(selectedTab()?.textContent).toBe('Quizzes')
  unmount()

  renderTabs('/videos/v1?tab=nonsense')
  expect(selectedTab()?.textContent).toBe('Chat')
})

it('writes the tab to the URL, replacing history and keeping other params', () => {
  renderTabs('/videos/v1?ref=library')
  fireEvent.click(screen.getByRole('tab', { name: 'Quizzes' }))
  expect(screen.getByTestId('location').textContent).toBe('REPLACE ?ref=library&tab=quizzes')
})
