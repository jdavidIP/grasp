import { API_URL, handleResponse } from './client'
import type { VideoDetail, VideoListItem } from '../types/video'

export function listVideos(): Promise<VideoListItem[]> {
  return fetch(`${API_URL}/videos`).then((res) => handleResponse(res))
}

export function createVideo(url: string): Promise<VideoListItem> {
  return fetch(`${API_URL}/videos`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  }).then((res) => handleResponse(res))
}

export function deleteVideo(id: string): Promise<void> {
  return fetch(`${API_URL}/videos/${id}`, { method: 'DELETE' }).then((res) => handleResponse(res))
}

export function getVideo(id: string): Promise<VideoDetail> {
  return fetch(`${API_URL}/videos/${id}`).then((res) => handleResponse(res))
}

export function reprocessVideo(id: string): Promise<VideoListItem> {
  return fetch(`${API_URL}/videos/${id}/reprocess`, { method: 'POST' }).then((res) =>
    handleResponse(res),
  )
}
