import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { THEME_KEY, initialTheme, useTheme } from './theme'

function stubSystemDark(dark: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: dark && query === '(prefers-color-scheme: dark)',
  }))
}

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

it('uses the stored theme over the system preference', () => {
  stubSystemDark(true)
  localStorage.setItem(THEME_KEY, 'light')
  expect(initialTheme()).toBe('light')
})

it('follows the system preference when nothing is stored', () => {
  stubSystemDark(true)
  expect(initialTheme()).toBe('dark')
  stubSystemDark(false)
  expect(initialTheme()).toBe('light')
})

it('ignores a stored value that is not a theme', () => {
  stubSystemDark(false)
  localStorage.setItem(THEME_KEY, 'purple')
  expect(initialTheme()).toBe('light')
})

it('falls back to the system preference when storage is blocked', () => {
  stubSystemDark(true)
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  expect(initialTheme()).toBe('dark')
})

it('toggles data-theme on <html> and persists the choice', () => {
  stubSystemDark(false)
  const { result } = renderHook(() => useTheme())
  expect(document.documentElement.getAttribute('data-theme')).toBeNull()

  act(() => result.current[1]())
  expect(result.current[0]).toBe('dark')
  expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  expect(localStorage.getItem(THEME_KEY)).toBe('dark')

  // A header mounted later (another page) starts from the saved choice.
  expect(renderHook(() => useTheme()).result.current[0]).toBe('dark')
})

it('still toggles for the session when storage is blocked', () => {
  stubSystemDark(false)
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  const { result } = renderHook(() => useTheme())
  act(() => result.current[1]())
  expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
})

it('keeps a toggled theme across pages when storage is blocked', () => {
  stubSystemDark(false)
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  const first = renderHook(() => useTheme())
  act(() => first.result.current[1]())
  first.unmount()

  // The next page mounts its own header; it must not fall back to the system theme.
  const next = renderHook(() => useTheme())
  expect(next.result.current[0]).toBe('dark')
  expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
})
