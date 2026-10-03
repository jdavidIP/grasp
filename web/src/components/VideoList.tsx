import { Link } from 'react-router'
import { useDeleteVideo } from '../hooks/useVideos'
import { formatRelative, formatTime } from '../lib/time'
import type { VideoListItem } from '../types/video'
import { useToast } from '../lib/toast'

interface VideoListProps {
  videos: VideoListItem[]
}

const TAG_CLASS: Record<VideoListItem['status'], string> = {
  ready: 'tag-accent',
  failed: 'tag-outline',
  pending: 'tag-neutral',
  processing: 'tag-neutral',
}

export function VideoList({ videos }: VideoListProps) {
  const deleteVideo = useDeleteVideo()
  const toast = useToast()

  if (videos.length === 0) {
    return <p className="text-muted library-empty">No videos yet. Add one above to get started.</p>
  }

  function handleDelete(video: VideoListItem) {
    if (
      !window.confirm(
        `Delete "${video.title}"? This removes its chat history, flashcards, and quizzes too, and cannot be undone.`,
      )
    ) {
      return
    }
    deleteVideo.mutate(video.id, { onSuccess: () => toast('Video deleted') })
  }

  return (
    <ul className="library-list">
      {videos.map((video) => (
        <li key={video.id} className="library-row">
          <Link to={`/videos/${video.id}`} className="library-row-link">
            <span className="library-thumb">
              {video.thumbnail_url && <img src={video.thumbnail_url} alt="" />}
              {video.duration_seconds !== null && (
                <span className="library-duration tabular">{formatTime(video.duration_seconds)}</span>
              )}
            </span>
            <span className="library-text">
              <span className="library-title">{video.title}</span>
              <span className="text-muted library-sub">
                {video.channel ? `${video.channel} · ` : ''}added {formatRelative(video.created_at)}
              </span>
              {video.status === 'failed' && video.error_message && (
                <span role="alert" className="library-note library-note-error">
                  {video.error_message}
                </span>
              )}
              {(video.status === 'pending' || video.status === 'processing') && (
                <span className="text-muted library-note">
                  Processing — this can take a few minutes for long videos.
                </span>
              )}
            </span>
          </Link>
          <span className="library-actions">
            <span className={`tag ${TAG_CLASS[video.status]} library-tag`}>{video.status}</span>
            <button
              type="button"
              className="btn btn-ghost library-delete"
              onClick={() => handleDelete(video)}
              disabled={deleteVideo.isPending}
            >
              Delete
            </button>
          </span>
          {deleteVideo.isError && deleteVideo.variables === video.id && (
            <p role="alert" className="library-note library-note-error library-row-error">
              {deleteVideo.error.message}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}
