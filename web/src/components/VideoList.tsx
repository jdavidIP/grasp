import { Link } from 'react-router'
import { useDeleteVideo } from '../hooks/useVideos'
import type { VideoListItem } from '../types/video'

interface VideoListProps {
  videos: VideoListItem[]
}

export function VideoList({ videos }: VideoListProps) {
  const deleteVideo = useDeleteVideo()

  if (videos.length === 0) {
    return <p>No videos yet. Add one above to get started.</p>
  }

  function handleDelete(video: VideoListProps['videos'][number]) {
    if (
      !window.confirm(
        `Delete "${video.title}"? This removes its chat history, flashcards, and quizzes too, and cannot be undone.`,
      )
    ) {
      return
    }
    deleteVideo.mutate(video.id)
  }

  return (
    <ul>
      {videos.map((video) => (
        <li key={video.id}>
          {video.thumbnail_url && <img src={video.thumbnail_url} alt="" width={120} />}
          <Link to={`/videos/${video.id}`}>{video.title}</Link>
          <span className={video.status === 'failed' ? 'status-failed' : undefined}>
            {video.status}
          </span>
          {video.status === 'failed' && video.error_message && (
            <p role="alert" className="status-failed">
              {video.error_message}
            </p>
          )}
          <button type="button" onClick={() => handleDelete(video)} disabled={deleteVideo.isPending}>
            Delete
          </button>
          {deleteVideo.isError && deleteVideo.variables === video.id && (
            <p role="alert">{deleteVideo.error.message}</p>
          )}
        </li>
      ))}
    </ul>
  )
}
