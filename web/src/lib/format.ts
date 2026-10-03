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
