import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import type { AttemptResult, Quiz } from '../types/quiz'
import { QuizResults, QuizResultsFor } from './QuizResults'

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
      id: 'b',
      order_index: 0,
      question_type: 'multi_select',
      prompt: 'Which are loops?',
      difficulty: 'medium',
      options: [
        { id: 'b1', text: 'for', order_index: 0 },
        { id: 'b2', text: 'while', order_index: 1 },
        { id: 'b3', text: 'if', order_index: 2 },
        { id: 'b4', text: 'try', order_index: 3 },
      ],
    },
    {
      id: 'c',
      order_index: 1,
      question_type: 'true_false',
      prompt: 'Lists use square brackets.',
      difficulty: 'easy',
      options: [
        { id: 'c1', text: 'True', order_index: 0 },
        { id: 'c2', text: 'False', order_index: 1 },
      ],
    },
  ],
}

const result: AttemptResult = {
  attempt_id: 'x',
  score: 0,
  results: [
    {
      question_id: 'b',
      is_correct: false,
      selected_option_ids: ['b1', 'b3'],
      correct_option_ids: ['b1', 'b2'],
      explanation: 'for and while are loops.',
      segment_id: 's2',
      source_start_time: 298,
    },
    {
      question_id: 'c',
      is_correct: false,
      selected_option_ids: [],
      correct_option_ids: ['c1'],
      explanation: 'Square brackets make a list.',
      segment_id: null,
      source_start_time: null,
    },
  ],
}

it('shows the score and marks every option against your answer', () => {
  const onSeek = vi.fn()
  render(<QuizResults quiz={quiz} result={result} onSeek={onSeek} />)

  expect(screen.getByText('0%')).toBeTruthy()
  expect(screen.getByText('0 of 2 correct · all-or-nothing, no partial credit')).toBeTruthy()
  const options = within(screen.getByRole('list', { name: 'Options for question 1' }))
  expect(options.getByText('for').closest('li')?.textContent).toContain('your answer · correct')
  expect(options.getByText('while').closest('li')?.textContent).toContain('correct answer')
  expect(options.getByText('if').closest('li')?.textContent).toContain('your answer')
  expect(options.getByText('try').closest('li')?.textContent).not.toContain('answer')

  fireEvent.click(screen.getByRole('button', { name: 'Jump to 4:58' }))
  expect(onSeek).toHaveBeenCalledWith(298)
})

it('says when a question was skipped and leaves out Jump without a time', () => {
  render(<QuizResults quiz={quiz} result={result} onSeek={() => {}} />)
  expect(screen.getByText('You skipped this question.')).toBeTruthy()
  expect(screen.getAllByRole('button', { name: /Jump to/ })).toHaveLength(1)
})

it('shows the error, not a blank screen, when the quiz behind a result cannot be fetched', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(500, { detail: 'Quiz lookup failed.' })))
  renderWithClient(<QuizResultsFor quizId="q1" result={result} onSeek={() => {}} />)
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Quiz lookup failed.')
})
