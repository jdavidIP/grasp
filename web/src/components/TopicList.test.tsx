import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'

import type { Segment } from '../types/video'
import { TopicList } from './TopicList'

const segment: Segment = {
  id: 's1',
  label: 'Loops',
  summary: 'For and while loops.',
  start_time: 298,
  end_time: 547,
}

it('seeks to a topic’s start when it is clicked', () => {
  const onSeek = vi.fn()
  render(<TopicList segments={[segment]} onSeek={onSeek} />)
  expect(screen.getByText('1 segment')).toBeTruthy()

  fireEvent.click(screen.getByRole('button', { name: /Loops/ }))
  expect(onSeek).toHaveBeenCalledWith(298)
  expect(screen.getByRole('button', { name: /Loops/ }).textContent).toContain('4:58–9:07')
})

it('says so when there are no topics yet', () => {
  render(<TopicList segments={[]} onSeek={vi.fn()} />)
  expect(screen.getByText('No topics yet.')).toBeTruthy()
  expect(screen.getByText('0 segments')).toBeTruthy()
})
