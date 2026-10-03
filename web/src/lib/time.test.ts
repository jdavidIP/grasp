import { expect, it } from 'vitest'

import { formatRelative, formatTime } from './time'

it('formats minutes under an hour and h:mm:ss from an hour up', () => {
  expect(formatTime(0)).toBe('0:00')
  expect(formatTime(59.9)).toBe('0:59')
  expect(formatTime(61)).toBe('1:01')
  expect(formatTime(3599)).toBe('59:59')
  expect(formatTime(3600)).toBe('1:00:00')
  expect(formatTime(10965)).toBe('3:02:45')
})

it('formats a past time relative to now in the largest fitting unit', () => {
  const now = new Date('2026-10-03T12:00:00Z')
  const ago = (seconds: number) => new Date(now.getTime() - seconds * 1000).toISOString()

  expect(formatRelative(ago(0), now)).toBe('now')
  expect(formatRelative(ago(30), now)).toBe('30 seconds ago')
  expect(formatRelative(ago(5 * 60), now)).toBe('5 minutes ago')
  expect(formatRelative(ago(3 * 3600), now)).toBe('3 hours ago')
  expect(formatRelative(ago(86400), now)).toBe('yesterday')
  expect(formatRelative(ago(3 * 86400), now)).toBe('3 days ago')
  expect(formatRelative(ago(60 * 86400), now)).toBe('2 months ago')
  expect(formatRelative(ago(400 * 86400), now)).toBe('last year')
})
