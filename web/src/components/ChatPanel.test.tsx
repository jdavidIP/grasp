import { fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import { ChatPanel } from './ChatPanel'

afterEach(() => {
  vi.unstubAllGlobals()
})

it('keeps the typed question and shows the error when sending fails', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_url: string, init?: RequestInit) =>
      init?.method === 'POST'
        ? jsonResponse(502, { detail: 'The answer service is unavailable.' })
        : jsonResponse(200, []),
    ),
  )
  renderWithClient(<ChatPanel videoId="v1" onSeek={() => {}} />)

  const input = screen.getByPlaceholderText('Ask about this video...')
  fireEvent.change(input, { target: { value: 'What is a for loop?' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))

  expect(await screen.findByRole('alert')).toHaveProperty(
    'textContent',
    'The answer service is unavailable.',
  )
  // Before the fix, the draft was cleared before the request settled, so a failed
  // send lost the question.
  expect(input).toHaveProperty('value', 'What is a for loop?')
})
