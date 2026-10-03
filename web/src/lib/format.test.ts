import { expect, it } from 'vitest'

import { STATUS_TAG, deckConfigSummary, plural } from './format'

it('pluralises a count', () => {
  expect(plural(0, 'segment')).toBe('0 segments')
  expect(plural(1, 'segment')).toBe('1 segment')
  expect(plural(7, 'video')).toBe('7 videos')
})

it('maps every status to its tag class', () => {
  expect(STATUS_TAG).toEqual({
    ready: 'tag-accent',
    failed: 'tag-outline',
    pending: 'tag-neutral',
    processing: 'tag-neutral',
  })
})

it('summarises a deck config', () => {
  expect(deckConfigSummary({ scope: 'whole_video', difficulty: 'mixed', style: 'concept' })).toBe(
    'Whole video · mixed · concept',
  )
  expect(
    deckConfigSummary({ scope: 'topics', segment_ids: ['a', 'b', 'c'], difficulty: 'hard', style: 'detail' }),
  ).toBe('3 topics · hard · detail')
  expect(deckConfigSummary({ scope: 'topics', segment_ids: ['a'], difficulty: 'easy', style: 'mixed' })).toBe(
    '1 topic · easy · mixed',
  )
  // An older or partial config leaves parts out instead of printing "undefined".
  expect(deckConfigSummary({ scope: 'whole_video' })).toBe('Whole video')
  expect(deckConfigSummary({})).toBe('')
})
