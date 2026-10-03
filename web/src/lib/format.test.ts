import { expect, it } from 'vitest'

import { STATUS_TAG, plural } from './format'

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
