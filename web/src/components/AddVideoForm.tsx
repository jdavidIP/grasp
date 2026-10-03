import { useState } from 'react'
import { useCreateVideo } from '../hooks/useVideos'
import { useToast } from '../lib/toast'

export function AddVideoForm() {
  const [url, setUrl] = useState('')
  const createVideo = useCreateVideo()
  const toast = useToast()

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    createVideo.mutate(url, {
      onSuccess: () => {
        setUrl('')
        toast('Video added — processing')
      },
    })
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="library-add">
        <input
          className="input library-add-input"
          type="url"
          placeholder="https://www.youtube.com/watch?v=…"
          aria-label="YouTube URL"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          required
        />
        <button type="submit" className="btn btn-primary blueprint library-add-button" disabled={createVideo.isPending}>
          <i className="corner tl" />
          <i className="corner tr" />
          <i className="corner bl" />
          <i className="corner br" />
          {createVideo.isPending ? 'Adding…' : 'Add video'}
        </button>
      </div>
      {createVideo.error && (
        <p role="alert" className="library-add-error">
          {createVideo.error.message}
        </p>
      )}
    </form>
  )
}
