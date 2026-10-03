import { screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { expect, it } from 'vitest'

import { renderWithClient } from '../test/render'
import type { VideoListItem } from '../types/video'
import { VideoList } from './VideoList'

function video(overrides: Partial<VideoListItem>): VideoListItem {
  return {
    id: 'v1',
    youtube_id: 'abc',
    title: 'A lecture',
    channel: 'Yale Courses',
    duration_seconds: 10965,
    thumbnail_url: 'https://img/v1.jpg',
    status: 'ready',
    error_message: null,
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

function renderList(videos: VideoListItem[]) {
  return renderWithClient(
    <MemoryRouter>
      <VideoList videos={videos} />
    </MemoryRouter>,
  )
}

it('renders a ready video with its tag, duration, channel line and no note', () => {
  renderList([video({})])
  const row = screen.getByRole('listitem')
  const tag = within(row).getByText('ready')
  expect(tag.className).toContain('tag-accent')
  expect(within(row).getByText('3:02:45')).toBeTruthy()
  expect(within(row).getByText(/^Yale Courses · added /)).toBeTruthy()
  expect(within(row).queryByRole('alert')).toBeNull()
  expect(within(row).queryByText(/Processing/)).toBeNull()
})

it('shows the error as an alert for a failed video', () => {
  renderList([video({ status: 'failed', error_message: 'No transcript available.' })])
  expect(screen.getByText('failed').className).toContain('tag-outline')
  expect(screen.getByRole('alert').textContent).toBe('No transcript available.')
})

it.each(['pending', 'processing'] as const)('shows the generic processing note while %s', (status) => {
  renderList([video({ status })])
  expect(screen.getByText(status).className).toContain('tag-neutral')
  expect(
    screen.getByText('Processing — this can take a few minutes for long videos.'),
  ).toBeTruthy()
})

it('handles a video with no thumbnail, channel or duration', () => {
  renderList([video({ thumbnail_url: null, channel: null, duration_seconds: null })])
  const row = screen.getByRole('listitem')
  expect(within(row).queryByRole('img')).toBeNull()
  expect(within(row).getByText(/^added /)).toBeTruthy()
  expect(row.textContent).not.toContain('null')
})

it('keeps Delete outside the link to the video', () => {
  renderList([video({})])
  const link = screen.getByRole('link')
  expect(link.getAttribute('href')).toBe('/videos/v1')
  expect(within(link).queryByRole('button')).toBeNull()
  expect(screen.getByRole('button', { name: 'Delete' })).toBeTruthy()
})

it('shows the empty state', () => {
  renderList([])
  expect(screen.getByText('No videos yet. Add one above to get started.')).toBeTruthy()
})
