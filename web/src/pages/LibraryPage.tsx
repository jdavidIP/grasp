import { AddVideoForm } from '../components/AddVideoForm'
import { AppHeader } from '../components/AppHeader'
import { VideoList } from '../components/VideoList'
import { useVideosQuery } from '../hooks/useVideos'
import { plural } from '../lib/format'
import './LibraryPage.css'

export function LibraryPage() {
  const { data: videos, isLoading, error } = useVideosQuery()
  const count = plural(videos?.length ?? 0, 'video')

  return (
    <>
      <AppHeader meta={videos ? count : ''} />
      <main className="library">
        <h1 className="library-heading">Library</h1>
        <p className="text-muted library-intro">
          Add a YouTube URL. Grasp fetches the transcript, splits it into topic segments, embeds the chunks,
          and then every answer, card and question can point back to a timestamp.
        </p>
        <AddVideoForm />
        {videos && (
          <div className="library-list-header">
            <h6>{count}</h6>
            <h6 className="text-muted">Newest first</h6>
          </div>
        )}
        {isLoading && <p className="text-muted library-empty">Loading…</p>}
        {error && (
          <p role="alert" className="library-add-error">
            {error.message}
          </p>
        )}
        {videos && <VideoList videos={videos} />}
      </main>
    </>
  )
}
