export type VideoStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface VideoListItem {
  id: string
  youtube_id: string
  title: string
  channel: string | null
  duration_seconds: number | null
  thumbnail_url: string | null
  status: VideoStatus
  created_at: string
}

export interface VideoDetail extends VideoListItem {
  error_message: string | null
  transcript_source: string | null
}
