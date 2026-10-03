import { fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import type { FlashcardDeck } from '../types/flashcard'
import type { Segment } from '../types/video'
import { FlashcardsPanel } from './FlashcardsPanel'

afterEach(() => {
  vi.unstubAllGlobals()
})

const segments: Segment[] = [
  { id: 's1', label: 'Intro', summary: 'Opening.', start_time: 0, end_time: 60 },
  { id: 's2', label: 'Loops', summary: 'For and while.', start_time: 60, end_time: 300 },
]

const newDeck: FlashcardDeck = {
  id: 'd9',
  video_id: 'v1',
  title: 'Fresh deck',
  config: {},
  created_at: '2026-10-03T12:00:00Z',
  cards: [
    {
      id: 'c1',
      front: 'What does range(3) yield?',
      back: '0, 1 and 2.',
      segment_id: 's2',
      source_start_time: 95,
      difficulty: 'easy',
      order_index: 0,
      note: null,
    },
  ],
}

function stubApi(post: () => Promise<Response>) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') return post()
    if (url.endsWith('/flashcard-decks/d9')) return jsonResponse(200, newDeck)
    return jsonResponse(200, [])
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function postedBody(fetchMock: ReturnType<typeof stubApi>): unknown {
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')
  return JSON.parse(String(call?.[1]?.body))
}

function renderPanel() {
  renderWithClient(<FlashcardsPanel videoId="v1" segments={segments} onSeek={() => {}} />)
}

it('goes from New deck through generating to reviewing the new deck', async () => {
  let resolve: (response: Response) => void = () => {}
  const fetchMock = stubApi(() => new Promise<Response>((r) => (resolve = r)))
  renderPanel()

  fireEvent.click(await screen.findByRole('button', { name: 'New deck' }))
  fireEvent.change(screen.getByRole('slider', { name: 'Number of cards' }), { target: { value: '20' } })
  fireEvent.click(screen.getByRole('button', { name: 'Generate 20 cards' }))

  expect(await screen.findByText('Generating deck…')).toBeTruthy()
  // The form is gone, so a second Generate can't fire.
  expect(screen.queryByRole('button', { name: /Generate/ })).toBeNull()
  expect(postedBody(fetchMock)).toEqual({ count: 20, scope: 'whole_video', difficulty: 'mixed', style: 'mixed' })

  resolve(jsonResponse(201, newDeck))
  expect(await screen.findByText('What does range(3) yield?')).toBeTruthy()
})

it('sends segment ids only for selected topics, and disables Generate until one is picked', async () => {
  const fetchMock = stubApi(async () => jsonResponse(201, newDeck))
  renderPanel()
  fireEvent.click(await screen.findByRole('button', { name: 'New deck' }))

  fireEvent.click(screen.getByRole('radio', { name: 'Selected topics' }))
  expect(screen.getByRole('button', { name: 'Select at least one topic' })).toHaveProperty('disabled', true)
  fireEvent.click(screen.getByRole('checkbox', { name: 'Loops' }))
  expect(screen.getByText('1 of 2 selected')).toBeTruthy()
  fireEvent.change(screen.getByLabelText('Title (generated if blank)'), { target: { value: '   ' } })
  fireEvent.click(screen.getByRole('button', { name: 'Generate 12 cards' }))

  await screen.findByText('What does range(3) yield?')
  expect(postedBody(fetchMock)).toEqual({
    count: 12,
    scope: 'topics',
    segment_ids: ['s2'],
    difficulty: 'mixed',
    style: 'mixed',
  })
})

it('returns to the form with the error and the draft when generation fails', async () => {
  stubApi(async () => jsonResponse(422, { detail: 'Could not generate any flashcards for this configuration.' }))
  renderPanel()
  fireEvent.click(await screen.findByRole('button', { name: 'New deck' }))
  fireEvent.change(screen.getByLabelText('Title (generated if blank)'), { target: { value: 'My deck' } })
  fireEvent.click(screen.getByRole('button', { name: 'Generate 12 cards' }))

  expect(await screen.findByRole('alert')).toHaveProperty(
    'textContent',
    'Could not generate any flashcards for this configuration.',
  )
  expect(screen.getByLabelText('Title (generated if blank)')).toHaveProperty('value', 'My deck')
})

it('returns to the list from Cancel', async () => {
  stubApi(async () => jsonResponse(201, newDeck))
  renderPanel()
  fireEvent.click(await screen.findByRole('button', { name: 'New deck' }))
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(await screen.findByRole('heading', { name: 'Flashcard decks' })).toBeTruthy()
})
