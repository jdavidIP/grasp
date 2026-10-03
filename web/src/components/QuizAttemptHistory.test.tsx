import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import { QuizAttemptHistory } from './QuizAttemptHistory'

afterEach(() => {
  vi.unstubAllGlobals()
})

it('shows the error instead of loading forever when the quiz fetch fails', async () => {
  const attempt = {
    id: 'a1',
    score: 0.5,
    correct_count: 1,
    question_count: 2,
    started_at: '2026-10-01T12:00:00Z',
    completed_at: '2026-10-01T12:05:00Z',
  }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.endsWith('/quizzes/q1')) return jsonResponse(500, { detail: 'Quiz lookup failed.' })
      if (url.endsWith('/quizzes/q1/attempts')) return jsonResponse(200, [attempt])
      return jsonResponse(200, attempt)
    }),
  )
  renderWithClient(<QuizAttemptHistory quizId="q1" onSeek={() => {}} onClose={() => {}} />)

  fireEvent.click(await screen.findByRole('button', { name: 'View' }))

  // Before the fix, a failed quiz fetch left the detail on "Loading attempt..." for
  // good, and no error was shown anywhere. Waiting for two copies of the error (the
  // list's and the detail's) checks the detail itself has settled on it.
  await waitFor(() => expect(screen.getAllByText('Quiz lookup failed.')).toHaveLength(2))
  expect(screen.queryByText('Loading attempt...')).toBeNull()
})
