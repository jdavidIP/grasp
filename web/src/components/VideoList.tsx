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

  return (
    <ul>
      {videos.map((video) => (
        <li key={video.id}>
          {video.thumbnail_url && <img src={video.thumbnail_url} alt="" width={120} />}
          <span>{video.title}</span>
          <span>{video.status}</span>
          <button
            type="button"
            onClick={() => deleteVideo.mutate(video.id)}
            disabled={deleteVideo.isPending}
          >
            Delete
          </button>
        </li>
      ))}
    </ul>
  )
}
