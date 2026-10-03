import { fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import type { QuizListItem } from '../types/quiz'
import { QuizList } from './QuizList'

afterEach(() => {
  vi.unstubAllGlobals()
})

function quiz(overrides: Partial<QuizListItem>): QuizListItem {
  return {
    id: 'q1',
    video_id: 'v1',
    title: 'Loops quiz',
    config: {},
    created_at: '2026-10-03T12:00:00Z',
    question_count: 6,
    best_score: 0.834,
    attempt_count: 3,
    ...overrides,
  }
}

function stubQuizzes(quizzes: QuizListItem[]) {
  const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => jsonResponse(200, quizzes))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderList() {
  renderWithClient(<QuizList videoId="v1" onNew={() => {}} onTake={() => {}} onHistory={() => {}} />)
}

it('shows the best score and the question and attempt counts', async () => {
  stubQuizzes([
    quiz({}),
    quiz({ id: 'q2', title: 'Fresh', question_count: 1, best_score: null, attempt_count: 0 }),
  ])
  renderList()
  expect(await screen.findByText('Best 83%')).toBeTruthy()
  expect(screen.getByText('6 questions · 3 attempts')).toBeTruthy()
  expect(screen.getByText('Never attempted')).toBeTruthy()
  expect(screen.getByText('1 question · 0 attempts')).toBeTruthy()
})

it('sends nothing when Delete is cancelled', async () => {
  const fetchMock = stubQuizzes([quiz({})])
  vi.stubGlobal('confirm', vi.fn(() => false))
  renderList()
  fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
})
