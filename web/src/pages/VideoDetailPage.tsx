import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { ChatPanel } from '../components/ChatPanel'
import { YouTubePlayer } from '../components/YouTubePlayer'
import { useReprocessVideo, useVideoQuery } from '../hooks/useVideos'
import { formatTime } from '../lib/time'

export function VideoDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: video, isLoading, error } = useVideoQuery(id!)
  const reprocess = useReprocessVideo(id!)
  const [seekSeconds, setSeekSeconds] = useState<number | null>(null)

  return (
    <main>
      <Link to="/">← Library</Link>
      {isLoading && <p>Loading...</p>}
      {error && <p role="alert">{error.message}</p>}
      {video && (
        <>
          <h1>{video.title}</h1>
          <span className={video.status === 'failed' ? 'status-failed' : undefined}>
            {video.status}
          </span>
          {video.status === 'failed' && video.error_message && (
            <p role="alert" className="status-failed">
              {video.error_message}
            </p>
          )}

          {video.status !== 'pending' && video.status !== 'processing' && (
            <button type="button" onClick={() => reprocess.mutate()} disabled={reprocess.isPending}>
              Reprocess
            </button>
          )}

          {video.status === 'ready' && (
            <YouTubePlayer videoId={video.youtube_id} seekSeconds={seekSeconds} />
          )}

          <h2>Topics</h2>
          {video.segments.length === 0 ? (
            <p>No topics yet.</p>
          ) : (
            <ul>
              {video.segments.map((segment) => (
                <li key={segment.id}>
                  <strong>{segment.label}</strong>{' '}
                  <span>
                    {formatTime(segment.start_time)}–{formatTime(segment.end_time)}
                  </span>
                  <p>{segment.summary}</p>
                </li>
              ))}
            </ul>
          )}

          {video.status === 'ready' && <ChatPanel videoId={video.id} onSeek={setSeekSeconds} />}
        </>
      )}
    </main>
  )
}
