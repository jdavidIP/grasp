import { afterEach, expect, test, vi } from 'vitest'
import { apiFetch } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})

// Real timers with a tiny timeout: fake timers don't drive jsdom's AbortSignal.timeout.
test('a request the server never answers rejects with a readable timeout error', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(
      (_url: string, init: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => reject(init.signal?.reason))
        }),
    ),
  )

  await expect(apiFetch('/videos', undefined, 10)).rejects.toThrow(
    'The server took too long to answer. Try again.',
  )
})
