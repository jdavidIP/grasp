import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import type { AttemptResult, Quiz } from '../types/quiz'
import { QuizTake } from './QuizTake'

afterEach(() => {
  vi.unstubAllGlobals()
})

const quiz: Quiz = {
  id: 'q1',
  video_id: 'v1',
  title: 'Loops quiz',
  config: {},
  created_at: '',
  questions: [
    {
      id: 'a',
      order_index: 0,
      question_type: 'multiple_choice',
      prompt: 'Which keyword starts a loop?',
      difficulty: 'easy',
      options: [
        { id: 'a1', text: 'for', order_index: 0 },
        { id: 'a2', text: 'def', order_index: 1 },
        { id: 'a3', text: 'try', order_index: 2 },
      ],
    },
    {
      id: 'b',
      order_index: 1,
      question_type: 'multi_select',
      prompt: 'Which are loops?',
      difficulty: 'medium',
      options: [
        { id: 'b1', text: 'for', order_index: 0 },
        { id: 'b2', text: 'while', order_index: 1 },
        { id: 'b3', text: 'if', order_index: 2 },
      ],
    },
  ],
}

const graded: AttemptResult = { attempt_id: 'x', score: 1, results: [] }

function stubApi() {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) =>
    init?.method === 'POST' ? jsonResponse(201, graded) : jsonResponse(200, quiz),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function posts(fetchMock: ReturnType<typeof stubApi>) {
  return fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')
}

function renderTake(onSubmitted = vi.fn(), onClose = vi.fn()) {
  renderWithClient(<QuizTake videoId="v1" quizId="q1" onSubmitted={onSubmitted} onClose={onClose} />)
  return { onSubmitted, onClose }
}

it('numbers the questions, labels their type, and counts answers', async () => {
  stubApi()
  renderTake()
  expect(await screen.findByText('01')).toBeTruthy()
  expect(screen.getByText('Multiple choice — one answer')).toBeTruthy()
  expect(screen.getByText('Select all that apply')).toBeTruthy()
  expect(screen.getAllByRole('radio')).toHaveLength(3)
  expect(screen.getAllByRole('checkbox')).toHaveLength(3)

  fireEvent.click(screen.getAllByRole('radio', { name: 'for' })[0])
  expect(screen.getByText('1 of 2 answered. Unanswered questions count as incorrect.')).toBeTruthy()
})

it('asks before submitting with unanswered questions, and sends nothing if cancelled', async () => {
  const fetchMock = stubApi()
  const confirm = vi.fn(() => false)
  vi.stubGlobal('confirm', confirm)
  renderTake()
  fireEvent.click(await screen.findByRole('button', { name: 'Submit' }))

  expect(confirm).toHaveBeenCalledWith(
    '2 of 2 questions are unanswered and will count as incorrect. Submit anyway?',
  )
  expect(posts(fetchMock)).toHaveLength(0)
})

it('submits a fully answered quiz without asking, once, and hands up the result', async () => {
  const fetchMock = stubApi()
  const confirm = vi.fn(() => true)
  vi.stubGlobal('confirm', confirm)
  const { onSubmitted } = renderTake()
  fireEvent.click(await screen.findByRole('radio', { name: 'for' }))
  fireEvent.click(screen.getByRole('checkbox', { name: 'while' }))
  const submit = screen.getByRole('button', { name: 'Submit' })
  fireEvent.click(submit)
  fireEvent.click(submit)

  await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith(graded))
  expect(confirm).not.toHaveBeenCalled()
  expect(posts(fetchMock)).toHaveLength(1)
  expect(JSON.parse(String(posts(fetchMock)[0][1]?.body))).toEqual({
    answers: [
      { question_id: 'a', selected_option_ids: ['a1'] },
      { question_id: 'b', selected_option_ids: ['b2'] },
    ],
  })
})

it('asks before closing only when something is selected', async () => {
  stubApi()
  const confirm = vi.fn(() => false)
  vi.stubGlobal('confirm', confirm)
  const { onClose } = renderTake()
  await screen.findByText('01')
  fireEvent.click(screen.getByRole('button', { name: 'Close' }))
  expect(confirm).not.toHaveBeenCalled()
  expect(onClose).toHaveBeenCalledTimes(1)

  fireEvent.click(screen.getByRole('radio', { name: 'for' }))
  fireEvent.click(screen.getByRole('button', { name: 'Close' }))
  expect(confirm).toHaveBeenCalledWith('Leave this quiz? Your answers so far will be lost.')
  expect(onClose).toHaveBeenCalledTimes(1)
})
