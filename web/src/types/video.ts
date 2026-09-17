export type VideoStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface VideoListItem {
  id: string
  youtube_id: string
  title: string
  channel: string | null
  duration_seconds: number | null
  thumbnail_url: string | null
  status: VideoStatus
  error_message: string | null
  created_at: string
}

export interface Segment {
  id: string
  label: string
  summary: string
  start_time: number
  end_time: number
}

export interface VideoDetail extends VideoListItem {
  transcript_source: string | null
  segments: Segment[]
}
