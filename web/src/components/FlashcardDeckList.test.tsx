import { fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import type { FlashcardDeckListItem } from '../types/flashcard'
import { FlashcardDeckList } from './FlashcardDeckList'

afterEach(() => {
  vi.unstubAllGlobals()
})

const deck: FlashcardDeckListItem = {
  id: 'd1',
  video_id: 'v1',
  title: 'Loops',
  config: { scope: 'topics', segment_ids: ['s1', 's2'], difficulty: 'hard', style: 'detail' },
  created_at: new Date().toISOString(),
  card_count: 12,
}

function stubDecks(decks: FlashcardDeckListItem[]) {
  const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => jsonResponse(200, decks))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

it('shows each deck with its card count, date and config summary', async () => {
  stubDecks([deck])
  const onReview = vi.fn()
  renderWithClient(<FlashcardDeckList videoId="v1" onNew={() => {}} onReview={onReview} />)

  expect(await screen.findByText('Loops')).toBeTruthy()
  expect(screen.getByText(/^12 cards · /)).toBeTruthy()
  expect(screen.getByText('2 topics · hard · detail')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Review' }))
  expect(onReview).toHaveBeenCalledWith('d1')
})

it('sends nothing when Delete is cancelled', async () => {
  const fetchMock = stubDecks([deck])
  vi.stubGlobal('confirm', vi.fn(() => false))
  renderWithClient(<FlashcardDeckList videoId="v1" onNew={() => {}} onReview={() => {}} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))

  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
})

it('says when there are no decks yet', async () => {
  stubDecks([])
  renderWithClient(<FlashcardDeckList videoId="v1" onNew={() => {}} onReview={() => {}} />)
  expect(await screen.findByText('No flashcard decks yet.')).toBeTruthy()
})
