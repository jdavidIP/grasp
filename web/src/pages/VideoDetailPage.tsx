import { Link, useParams } from 'react-router'
import { useReprocessVideo, useVideoQuery } from '../hooks/useVideos'

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

export function VideoDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: video, isLoading, error } = useVideoQuery(id!)
  const reprocess = useReprocessVideo(id!)

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
        </>
      )}
    </main>
  )
}
