import { apiFetch } from './client'
import type { VideoDetail, VideoListItem } from '../types/video'

export function listVideos(): Promise<VideoListItem[]> {
  return apiFetch('/videos')
}

export function createVideo(url: string): Promise<VideoListItem> {
  return apiFetch('/videos', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
}

export function deleteVideo(id: string): Promise<void> {
  return apiFetch(`/videos/${id}`, { method: 'DELETE' })
}

export function getVideo(id: string): Promise<VideoDetail> {
  return apiFetch(`/videos/${id}`)
}

export function reprocessVideo(id: string): Promise<VideoListItem> {
  return apiFetch(`/videos/${id}/reprocess`, { method: 'POST' })
}
