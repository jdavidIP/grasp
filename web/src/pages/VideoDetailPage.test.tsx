import { fireEvent, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, expect, it, vi } from 'vitest'

import { ToastProvider } from '../components/Toast'
import { jsonResponse, renderWithClient } from '../test/render'
import type { VideoDetail } from '../types/video'
import { VideoDetailPage } from './VideoDetailPage'

afterEach(() => {
  vi.unstubAllGlobals()
  delete window.YT
})

function video(overrides: Partial<VideoDetail>): VideoDetail {
  return {
    id: 'v1',
    youtube_id: 'abc123',
    title: 'A lecture',
    channel: 'YaleCourses',
    duration_seconds: 3375,
    thumbnail_url: null,
    status: 'ready',
    error_message: null,
    created_at: '2026-10-01T12:00:00Z',
    transcript_source: 'youtube',
    segments: [
      { id: 's1', label: 'Intro', summary: 'Opening.', start_time: 8, end_time: 148 },
      { id: 's2', label: 'Berlin', summary: 'The wall.', start_time: 232, end_time: 365 },
    ],
    ...overrides,
  }
}

function renderPage(detail: VideoDetail) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      url.endsWith('/videos/v1') ? jsonResponse(200, detail) : jsonResponse(200, []),
    ),
  )
  return renderWithClient(
    <ToastProvider>
      <MemoryRouter initialEntries={['/videos/v1']}>
        <Routes>
          <Route path="/videos/:id" element={<VideoDetailPage />} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>,
  )
}

it('shows channel, duration and segment count under the title', async () => {
  renderPage(video({}))
  expect(await screen.findByText('YaleCourses · 56:15 · 2 segments')).toBeTruthy()
  expect(screen.getByRole('heading', { name: 'A lecture' })).toBeTruthy()
})

it('leaves out a missing channel and duration and says "1 segment"', async () => {
  renderPage(
    video({
      channel: null,
      duration_seconds: null,
      segments: [{ id: 's1', label: 'Only', summary: 'One.', start_time: 0, end_time: 60 }],
    }),
  )
  expect(await screen.findByText('1 segment', { selector: '.workspace-meta' })).toBeTruthy()
  expect(document.body.textContent).not.toContain('null')
})

it('shows the tabs for a ready video and toasts each seek', async () => {
  renderPage(video({}))
  expect(await screen.findByRole('tablist', { name: 'Study tools' })).toBeTruthy()

  fireEvent.click(screen.getByRole('button', { name: /Berlin/ }))
  expect(screen.getByRole('status').textContent).toBe('Jumped to 3:52')
})

it('explains the wait instead of showing tabs while processing', async () => {
  renderPage(video({ status: 'processing', segments: [] }))
  expect(
    await screen.findByText('Chat, flashcards and quizzes open once the video is processed.'),
  ).toBeTruthy()
  expect(screen.queryByRole('tablist')).toBeNull()
  expect(screen.queryByRole('button', { name: 'Reprocess' })).toBeNull()
})

it('shows the failure, the error and Reprocess for a failed video', async () => {
  renderPage(video({ status: 'failed', error_message: 'No transcript available.', segments: [] }))
  expect(
    await screen.findByText(
      "This video couldn't be processed. Reprocess it to use chat, flashcards and quizzes.",
    ),
  ).toBeTruthy()
  expect(screen.getByRole('alert').textContent).toBe('No transcript available.')
  expect(screen.getByRole('button', { name: 'Reprocess' })).toBeTruthy()
  expect(screen.queryByRole('tablist')).toBeNull()
})

function reprocessCalls() {
  return vi
    .mocked(fetch)
    .mock.calls.filter(([url]) => String(url).endsWith('/reprocess'))
}

it('does not reprocess when the warning is cancelled', async () => {
  renderPage(video({}))
  vi.stubGlobal('confirm', vi.fn(() => false))
  fireEvent.click(await screen.findByRole('button', { name: 'Reprocess' }))

  expect(window.confirm).toHaveBeenCalledWith(
    "Reprocessing rebuilds this video's topics and deletes its chat history. Continue?",
  )
  expect(reprocessCalls()).toHaveLength(0)
})

it('reprocesses once the warning is confirmed', async () => {
  renderPage(video({}))
  vi.stubGlobal('confirm', vi.fn(() => true))
  fireEvent.click(await screen.findByRole('button', { name: 'Reprocess' }))

  // The mutation calls fetch on a later tick.
  await waitFor(() => expect(reprocessCalls()).toHaveLength(1))
})
