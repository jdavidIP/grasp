import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { TOAST_MS, useToast } from '../lib/toast'
import { ToastProvider } from './Toast'

function Trigger({ message }: { message: string }) {
  const show = useToast()
  return <button onClick={() => show(message)}>{message}</button>
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

it('shows a message in a polite status region and clears it after 1900ms', () => {
  render(
    <ToastProvider>
      <Trigger message="Saved" />
    </ToastProvider>,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Saved' }))
  expect(screen.getByRole('status').textContent).toBe('Saved')

  act(() => vi.advanceTimersByTime(TOAST_MS - 1))
  expect(screen.getByRole('status').textContent).toBe('Saved')
  act(() => vi.advanceTimersByTime(1))
  expect(screen.getByRole('status').textContent).toBe('')
})

it('replaces the current message and restarts the timer', () => {
  render(
    <ToastProvider>
      <Trigger message="First" />
      <Trigger message="Second" />
    </ToastProvider>,
  )
  fireEvent.click(screen.getByRole('button', { name: 'First' }))
  act(() => vi.advanceTimersByTime(1000))
  fireEvent.click(screen.getByRole('button', { name: 'Second' }))
  expect(screen.getByRole('status').textContent).toBe('Second')

  // The first message's timer would have fired here; the second must survive it.
  act(() => vi.advanceTimersByTime(1000))
  expect(screen.getByRole('status').textContent).toBe('Second')
  act(() => vi.advanceTimersByTime(TOAST_MS - 1000))
  expect(screen.getByRole('status').textContent).toBe('')
})
