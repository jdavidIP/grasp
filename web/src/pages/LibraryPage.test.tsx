import { screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithClient } from '../test/render'
import { LibraryPage } from './LibraryPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

function renderPage() {
  return renderWithClient(
    <MemoryRouter>
      <LibraryPage />
    </MemoryRouter>,
  )
}

it('does not claim an empty library while the list is loading', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {})))
  renderPage()
  expect(screen.getByText('Loading…')).toBeTruthy()
  expect(screen.queryByText('0 videos')).toBeNull()
})

it('does not claim an empty library when the list fails to load', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(500, { detail: 'Database unavailable.' })))
  renderPage()
  expect((await screen.findByRole('alert')).textContent).toBe('Database unavailable.')
  expect(screen.queryByText('0 videos')).toBeNull()
})

it('shows the count once the list has loaded', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, [])))
  renderPage()
  // The list header and the page header both show the count.
  await waitFor(() => expect(screen.getAllByText('0 videos')).toHaveLength(2))
})
