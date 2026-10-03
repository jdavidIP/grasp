import { fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import type { Flashcard, FlashcardDeck } from '../types/flashcard'
import type { Segment } from '../types/video'
import { FlashcardReview } from './FlashcardReview'

afterEach(() => {
  vi.unstubAllGlobals()
})

const segments: Segment[] = [{ id: 's2', label: 'Loops', summary: 'x', start_time: 60, end_time: 300 }]

function card(overrides: Partial<Flashcard>): Flashcard {
  return {
    id: 'c1',
    front: 'Front one',
    back: 'Back one',
    segment_id: 's2',
    source_start_time: 95,
    difficulty: 'easy',
    order_index: 0,
    note: null,
    ...overrides,
  }
}

function renderDeck(cards: Flashcard[], onSeek = vi.fn()) {
  const deck: FlashcardDeck = { id: 'd1', video_id: 'v1', title: 'Loops deck', config: {}, created_at: '', cards }
  vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, deck)))
  renderWithClient(<FlashcardReview deckId="d1" segments={segments} onSeek={onSeek} onClose={() => {}} />)
  return onSeek
}

function cellClasses(): string[] {
  return [...document.querySelectorAll('.fc-cell')].map((cell) => cell.className)
}

const twoCards = [
  card({ note: 'The video says 0 to 3; the speaker means 0 to 2.' }),
  card({
    id: 'c2',
    front: 'Front two',
    back: 'Back two',
    segment_id: null,
    source_start_time: null,
    difficulty: null,
  }),
]

it('shows the position, the topic and a progress strip', async () => {
  renderDeck(twoCards)
  expect(await screen.findByText('Front one')).toBeTruthy()
  expect(screen.getByText('Card 1 of 2')).toBeTruthy()
  expect(screen.getByText('Loops')).toBeTruthy()
  expect(cellClasses()).toEqual(['fc-cell fc-cell-current', 'fc-cell'])
})

it('reveals the back and the note with Space, and moves on with ArrowRight', async () => {
  renderDeck(twoCards)
  const section = await screen.findByRole('region', { name: 'Flashcard review' })
  await screen.findByText('Front one')

  fireEvent.keyDown(section, { key: ' ' })
  expect(screen.getByText('Back one')).toBeTruthy()
  expect(screen.getByText('The video says 0 to 3; the speaker means 0 to 2.')).toBeTruthy()

  fireEvent.keyDown(section, { key: 'ArrowRight' })
  expect(screen.getByText('Front two')).toBeTruthy()
  expect(screen.queryByText('Back two')).toBeNull()
  expect(cellClasses()).toEqual(['fc-cell fc-cell-past', 'fc-cell fc-cell-current'])
})

it('still moves with the arrows when a button has focus', async () => {
  renderDeck(twoCards)
  const next = await screen.findByRole('button', { name: 'Next →' })
  fireEvent.keyDown(next, { key: 'ArrowRight' })
  expect(screen.getByText('Front two')).toBeTruthy()
})

it('seeks from Jump without hiding the answer', async () => {
  const onSeek = renderDeck(twoCards)
  fireEvent.click(await screen.findByText('Front one'))
  fireEvent.click(screen.getByRole('button', { name: 'Jump to 1:35' }))
  expect(onSeek).toHaveBeenCalledWith(95)
  expect(screen.getByText('Back one')).toBeTruthy()
})

it('leaves out Jump and the topic when a card has neither, and disables the ends', async () => {
  renderDeck(twoCards)
  expect(await screen.findByRole('button', { name: '← Previous' })).toHaveProperty('disabled', true)
  fireEvent.click(screen.getByRole('button', { name: 'Next →' }))
  expect(screen.getByRole('button', { name: 'Next →' })).toHaveProperty('disabled', true)
  fireEvent.click(screen.getByRole('button', { name: 'Show answer' }))
  expect(screen.getByText('Back two')).toBeTruthy()
  expect(screen.queryByRole('button', { name: /Jump to/ })).toBeNull()
  expect(screen.queryByText('Loops')).toBeNull()
})

it('keeps focus in the review when a move removes the focused Jump button', async () => {
  renderDeck(twoCards)
  const section = await screen.findByRole('region', { name: 'Flashcard review' })
  fireEvent.click(await screen.findByText('Front one'))
  const jump = screen.getByRole('button', { name: 'Jump to 1:35' })
  jump.focus()

  fireEvent.keyDown(jump, { key: 'ArrowRight' })
  expect(screen.getByText('Front two')).toBeTruthy()
  // Jump is gone with the answer; focus must not fall out of the review.
  expect(document.activeElement).toBe(section)
})

it('keeps focus in the review when Next reaches the last card and is disabled', async () => {
  renderDeck(twoCards)
  const section = await screen.findByRole('region', { name: 'Flashcard review' })
  const next = await screen.findByRole('button', { name: 'Next →' })
  next.focus()

  fireEvent.click(next)
  expect(next).toHaveProperty('disabled', true)
  expect(document.activeElement).toBe(section)
})

it('ignores shortcuts pressed with a modifier key', async () => {
  renderDeck(twoCards)
  const section = await screen.findByRole('region', { name: 'Flashcard review' })
  await screen.findByText('Front one')

  // Alt+Right is the browser's Forward; Ctrl/Shift+Space are not ours either.
  fireEvent.keyDown(section, { key: 'ArrowRight', altKey: true })
  fireEvent.keyDown(section, { key: ' ', ctrlKey: true })
  fireEvent.keyDown(section, { key: ' ', shiftKey: true })
  expect(screen.getByText('Card 1 of 2')).toBeTruthy()
  expect(screen.queryByText('Back one')).toBeNull()
})
