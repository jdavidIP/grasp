import { fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import type { ChatMessage, ChatSource } from '../types/chat'
import { ChatPanel } from './ChatPanel'

afterEach(() => {
  vi.unstubAllGlobals()
})

function exchange(answer: Partial<ChatMessage>): ChatMessage[] {
  return [
    {
      id: 'm1',
      role: 'user',
      content: 'What is a for loop?',
      created_at: '2026-10-03T12:00:00Z',
      sources: [],
      grounded: null,
    },
    {
      id: 'm2',
      role: 'assistant',
      content: 'A loop over items.',
      created_at: '2026-10-03T12:00:01Z',
      sources: [],
      grounded: true,
      ...answer,
    },
  ]
}

const chunkSource: ChatSource = {
  chunk_id: 'c1',
  segment_label: 'Loops',
  start_time: 95,
  end_time: 120,
  text: 'for x in items',
}

function stubFetch(history: ChatMessage[], post?: () => Promise<Response>) {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.method === 'POST' && post) return post()
    if (init?.method === 'DELETE') return new Response(null, { status: 204 })
    return jsonResponse(200, history)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function input() {
  return screen.getByRole('textbox', { name: 'Ask about this video' })
}

it('shows a reloaded answer with its sources, and a source seeks', async () => {
  stubFetch(exchange({ sources: [chunkSource] }))
  const onSeek = vi.fn()
  renderWithClient(<ChatPanel videoId="v1" onSeek={onSeek} />)

  expect(await screen.findByText('A loop over items.')).toBeTruthy()
  expect(screen.getByRole('heading', { name: 'Sources' })).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: /Loops @ 1:35/ }))
  expect(onSeek).toHaveBeenCalledWith(95)
})

it("labels a broad answer's sources as segment summaries with their span", async () => {
  stubFetch(
    exchange({
      sources: [{ chunk_id: null, segment_label: 'Intro', start_time: 8, end_time: 148, text: 'Opening.' }],
    }),
  )
  renderWithClient(<ChatPanel videoId="v1" onSeek={() => {}} />)

  expect(await screen.findByRole('heading', { name: 'Sources — segment summaries' })).toBeTruthy()
  expect(screen.getByRole('button', { name: /Intro @ 0:08–2:28/ })).toBeTruthy()
})

it("tags an answer the video doesn't cover and lists no sources", async () => {
  stubFetch(exchange({ grounded: false, sources: [chunkSource] }))
  renderWithClient(<ChatPanel videoId="v1" onSeek={() => {}} />)

  expect(await screen.findByText('Not covered in this video')).toBeTruthy()
  expect(screen.queryByRole('heading', { name: /Sources/ })).toBeNull()
})

it('shows the question and "Retrieving…" while the answer is on its way', async () => {
  stubFetch([], () => new Promise<Response>(() => {}))
  renderWithClient(<ChatPanel videoId="v1" onSeek={() => {}} />)
  await screen.findByText('Ask anything about this video.')

  fireEvent.change(input(), { target: { value: 'What is recursion?' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))

  expect(await screen.findByText('What is recursion?')).toBeTruthy()
  expect(screen.getByText('Retrieving…')).toBeTruthy()
})

it('keeps the typed question and shows the error when sending fails', async () => {
  stubFetch([], async () => jsonResponse(502, { detail: 'The answer service is unavailable.' }))
  renderWithClient(<ChatPanel videoId="v1" onSeek={() => {}} />)
  await screen.findByText('Ask anything about this video.')

  fireEvent.change(input(), { target: { value: 'What is a for loop?' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))

  expect(await screen.findByRole('alert')).toHaveProperty(
    'textContent',
    'The answer service is unavailable.',
  )
  // Before the fix, the draft was cleared before the request settled, so a failed
  // send lost the question.
  expect(input()).toHaveProperty('value', 'What is a for loop?')
  expect(screen.queryByText('Retrieving…')).toBeNull()
})

it('disables Send for a blank question', async () => {
  stubFetch([])
  renderWithClient(<ChatPanel videoId="v1" onSeek={() => {}} />)
  await screen.findByText('Ask anything about this video.')

  fireEvent.change(input(), { target: { value: '   ' } })
  expect(screen.getByRole('button', { name: 'Send' })).toHaveProperty('disabled', true)
})

it('sends nothing when Clear is cancelled', async () => {
  const fetchMock = stubFetch(exchange({}))
  vi.stubGlobal('confirm', vi.fn(() => false))
  renderWithClient(<ChatPanel videoId="v1" onSeek={() => {}} />)
  await screen.findByText('A loop over items.')

  fireEvent.click(screen.getByRole('button', { name: 'Clear' }))
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
})
