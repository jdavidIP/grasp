import { render, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { YouTubePlayer } from './YouTubePlayer'

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
    <div>{ready ? <YouTubePlayer videoId="abc" seekSeconds={null} /> : <p>Processing</p>}</div>
  )
  const { rerender, container } = render(page(true))
  await waitFor(() => expect(Player).toHaveBeenCalled())
  expect(container.querySelector('iframe')).not.toBeNull()

  expect(() => rerender(page(false))).not.toThrow()
  expect(container.textContent).toBe('Processing')
})
