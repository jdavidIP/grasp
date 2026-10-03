import type { VideoStatus } from '../types/video'

export function plural(n: number, word: string): string {
  return `${n} ${n === 1 ? word : `${word}s`}`
}

export const STATUS_TAG: Record<VideoStatus, string> = {
  ready: 'tag-accent',
  failed: 'tag-outline',
  pending: 'tag-neutral',
  processing: 'tag-neutral',
}

// One line describing a deck's stored config, e.g. "3 topics · hard · detail". Parts
// missing from an older or partial config are left out.
export function deckConfigSummary(config: Record<string, unknown>): string {
  const { scope, segment_ids: segmentIds, difficulty, style } = config
  const scopePart =
    scope === 'whole_video'
      ? 'Whole video'
      : scope === 'topics' && Array.isArray(segmentIds)
        ? plural(segmentIds.length, 'topic')
        : null
  return [scopePart, difficulty, style]
    .filter((part): part is string => typeof part === 'string')
    .join(' · ')
}
