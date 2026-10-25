import { render, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { YouTubePlayer } from './YouTubePlayer'

// YouTubePlayer caches its API-loading promise at module level. Each test sets window.YT
// before rendering, and the cached promise only reads window.YT when it resolves, so
// tests in this file can share it.
afterEach(() => {
  delete window.YT
})

it('survives being unmounted after the IFrame API replaces its target (#25)', async () => {
  // The real API swaps the element it's given for an <iframe>, a DOM change React
  // never sees. Before the fix, that element was the div React rendered, so React
  // later tried to remove a node that was no longer in the document.
  const Player = vi.fn(function (element: HTMLElement) {
    element.replaceWith(document.createElement('iframe'))
    return { seekTo: vi.fn(), playVideo: vi.fn(), destroy: vi.fn() }
  })
  window.YT = { Player } as unknown as NonNullable<Window['YT']>

  // As on the video page: the parent stays mounted while the player is swapped out
  // (Reprocess flips the video from ready to processing).
  const page = (ready: boolean) => (
    <div>{ready ? <YouTubePlayer videoId="abc" seek={null} /> : <p>Processing</p>}</div>
  )
  const { rerender, container } = render(page(true))
  await waitFor(() => expect(Player).toHaveBeenCalled())
  expect(container.querySelector('iframe')).not.toBeNull()

  expect(() => rerender(page(false))).not.toThrow()
  expect(container.textContent).toBe('Processing')
})

it('seeks every time it is asked, even to the same time twice', async () => {
  const seekTo = vi.fn()
  const playVideo = vi.fn()
  const Player = vi.fn(function () {
    return { seekTo, playVideo, destroy: vi.fn() }
  })
  window.YT = { Player } as unknown as NonNullable<Window['YT']>

  const { rerender } = render(<YouTubePlayer videoId="abc" seek={null} />)
  await waitFor(() => expect(Player).toHaveBeenCalled())

  rerender(<YouTubePlayer videoId="abc" seek={{ seconds: 30, id: 1 }} />)
  rerender(<YouTubePlayer videoId="abc" seek={{ seconds: 30, id: 2 }} />)

  expect(seekTo).toHaveBeenCalledTimes(2)
  expect(seekTo).toHaveBeenLastCalledWith(30, true)
  expect(playVideo).toHaveBeenCalledTimes(2)
})

it('leaves only the current player in its frame when the video changes', async () => {
  const Player = vi.fn(function (element: HTMLElement) {
    element.replaceWith(document.createElement('iframe'))
    return { seekTo: vi.fn(), playVideo: vi.fn(), destroy: vi.fn() }
  })
  window.YT = { Player } as unknown as NonNullable<Window['YT']>

  const { container, rerender } = render(<YouTubePlayer videoId="abc" seek={null} />)
  await waitFor(() => expect(Player).toHaveBeenCalledTimes(1))
  rerender(<YouTubePlayer videoId="def" seek={null} />)
  await waitFor(() => expect(Player).toHaveBeenCalledTimes(2))

  // Each run's cleanup must take its own target (or the iframe that replaced it) with it.
  expect(container.querySelector('.youtube-player')?.children).toHaveLength(1)
})
