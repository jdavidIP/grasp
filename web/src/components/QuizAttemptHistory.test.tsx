import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import type { AttemptListItem } from '../types/quiz'
import { QuizAttemptDetail, QuizAttemptHistory } from './QuizAttemptHistory'

afterEach(() => {
  vi.unstubAllGlobals()
})

const attempts: AttemptListItem[] = [
  {
    id: 'a2',
    score: 0.75,
    correct_count: 3,
    question_count: 4,
    started_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
  },
  {
    id: 'a1',
    score: 0.5,
    correct_count: 2,
    question_count: 4,
    started_at: '2026-10-01T12:00:00Z',
    completed_at: '2026-10-01T12:05:00Z',
  },
]

it('lists attempts with counts and scores, and opens one', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      url.endsWith('/attempts')
        ? jsonResponse(200, attempts)
        : jsonResponse(200, { id: 'q1', title: 'Loops quiz', questions: [] }),
    ),
  )
  const onOpen = vi.fn()
  const onTakeAgain = vi.fn()
  renderWithClient(
    <QuizAttemptHistory quizId="q1" onOpen={onOpen} onTakeAgain={onTakeAgain} onClose={() => {}} />,
  )

  expect(await screen.findByText('3 / 4')).toBeTruthy()
  expect(screen.getByText('75%')).toBeTruthy()
  expect(screen.getByText('2 / 4')).toBeTruthy()
  fireEvent.click(screen.getAllByRole('button', { name: /^View attempt from/ })[0])
  expect(onOpen).toHaveBeenCalledWith('a2')
  fireEvent.click(screen.getByRole('button', { name: 'Take it again' }))
  expect(onTakeAgain).toHaveBeenCalled()
})

it('shows the error instead of loading forever when the quiz fetch fails', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      url.endsWith('/quizzes/q1')
        ? jsonResponse(500, { detail: 'Quiz lookup failed.' })
        : jsonResponse(200, attempts[0]),
    ),
  )
  renderWithClient(<QuizAttemptDetail quizId="q1" attemptId="a1" onSeek={() => {}} />)
  await waitFor(() => expect(screen.getByText('Quiz lookup failed.')).toBeTruthy())
  expect(screen.queryByText('Loading…')).toBeNull()
})
