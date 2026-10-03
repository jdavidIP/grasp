import { fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import type { Quiz } from '../types/quiz'
import type { Segment } from '../types/video'
import { QuizzesPanel } from './QuizzesPanel'

afterEach(() => {
  vi.unstubAllGlobals()
})

const segments: Segment[] = [
  { id: 's1', label: 'Intro', summary: 'x', start_time: 0, end_time: 60 },
  { id: 's2', label: 'Loops', summary: 'y', start_time: 60, end_time: 300 },
]

const newQuiz: Quiz = {
  id: 'q9',
  video_id: 'v1',
  title: 'Fresh quiz',
  config: {},
  created_at: '2026-10-03T12:00:00Z',
  questions: [
    {
      id: 'qq1',
      order_index: 0,
      question_type: 'true_false',
      prompt: 'Python lists use square brackets.',
      difficulty: 'easy',
      options: [
        { id: 'o1', text: 'True', order_index: 0 },
        { id: 'o2', text: 'False', order_index: 1 },
      ],
    },
  ],
}

function stubApi(post: () => Promise<Response>) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') return post()
    if (url.endsWith('/quizzes/q9')) return jsonResponse(200, newQuiz)
    return jsonResponse(200, [])
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function postedBody(fetchMock: ReturnType<typeof stubApi>): unknown {
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')
  return JSON.parse(String(call?.[1]?.body))
}

async function openConfig() {
  renderWithClient(<QuizzesPanel videoId="v1" segments={segments} onSeek={() => {}} />)
  fireEvent.click(await screen.findByRole('button', { name: 'New quiz' }))
}

it('goes from New quiz through generating to taking the new quiz, with the default payload', async () => {
  let resolve: (response: Response) => void = () => {}
  const fetchMock = stubApi(() => new Promise<Response>((r) => (resolve = r)))
  await openConfig()
  fireEvent.click(screen.getByRole('button', { name: 'Generate 6 questions' }))

  expect(await screen.findByText('Generating quiz…')).toBeTruthy()
  expect(postedBody(fetchMock)).toEqual({
    count: 6,
    scope: 'whole_video',
    question_types: ['multiple_choice', 'multi_select', 'true_false'],
    options_per_question: 4,
    difficulty: 'mixed',
  })
  resolve(jsonResponse(201, newQuiz))
  expect(await screen.findByText('Python lists use square brackets.')).toBeTruthy()
})

it('keeps the last question type checked and drops options per question for true/false only', async () => {
  const fetchMock = stubApi(async () => jsonResponse(201, newQuiz))
  await openConfig()
  fireEvent.click(screen.getByRole('checkbox', { name: /^Multiple choice/ }))
  fireEvent.click(screen.getByRole('checkbox', { name: /^Select all that apply/ }))
  const trueFalse = screen.getByRole('checkbox', { name: /^True \/ false/ })
  expect(trueFalse).toHaveProperty('disabled', true)
  expect(screen.getByText('At least one type is required.')).toBeTruthy()
  expect(screen.queryByRole('radiogroup', { name: 'Options per question' })).toBeNull()

  fireEvent.click(screen.getByRole('radio', { name: 'Selected topics' }))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Loops' }))
  fireEvent.click(screen.getByRole('button', { name: 'Generate 6 questions' }))

  await screen.findByText('Python lists use square brackets.')
  expect(postedBody(fetchMock)).toEqual({
    count: 6,
    scope: 'topics',
    segment_ids: ['s2'],
    question_types: ['true_false'],
    difficulty: 'mixed',
  })
})

it('returns to the form with the error and the draft when generation fails', async () => {
  stubApi(async () => jsonResponse(422, { detail: 'Could not generate any questions for this configuration.' }))
  await openConfig()
  fireEvent.change(screen.getByLabelText('Title (generated if blank)'), { target: { value: 'Mine' } })
  fireEvent.click(screen.getByRole('button', { name: 'Generate 6 questions' }))

  expect(await screen.findByRole('alert')).toHaveProperty(
    'textContent',
    'Could not generate any questions for this configuration.',
  )
  expect(screen.getByLabelText('Title (generated if blank)')).toHaveProperty('value', 'Mine')
})

it('returns to the list from Cancel', async () => {
  stubApi(async () => jsonResponse(201, newQuiz))
  await openConfig()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(await screen.findByRole('heading', { name: 'Quizzes' })).toBeTruthy()
})
