import { AddVideoForm } from '../components/AddVideoForm'
import { VideoList } from '../components/VideoList'
import { useVideosQuery } from '../hooks/useVideos'

export function LibraryPage() {
  const { data: videos, isLoading, error } = useVideosQuery()

  return (
    <main>
      <h1>Grasp</h1>
      <AddVideoForm />
      {isLoading && <p>Loading...</p>}
      {error && <p role="alert">{error.message}</p>}
      {videos && <VideoList videos={videos} />}
    </main>
  )
}
