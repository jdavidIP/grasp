import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { AppHeader } from './AppHeader'

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
  vi.stubGlobal('matchMedia', () => ({ matches: false }))
})

afterEach(() => {
  vi.unstubAllGlobals()
})

it('links the brand home, shows the meta text, and toggles the theme', () => {
  render(
    <MemoryRouter>
      <AppHeader meta="3 videos" />
    </MemoryRouter>,
  )

  expect(screen.getByRole('link', { name: 'GRASP' }).getAttribute('href')).toBe('/')
  expect(screen.getByText('3 videos')).toBeTruthy()

  fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }))
  expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  expect(screen.getByRole('button', { name: 'Switch to light theme' })).toBeTruthy()
})
