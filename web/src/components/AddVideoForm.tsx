import { useState } from 'react'
import { useCreateVideo } from '../hooks/useVideos'

export function AddVideoForm() {
  const [url, setUrl] = useState('')
  const createVideo = useCreateVideo()

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    createVideo.mutate(url, {
      onSuccess: () => setUrl(''),
    })
  }

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="url"
        placeholder="https://www.youtube.com/watch?v=..."
        value={url}
        onChange={(event) => setUrl(event.target.value)}
        required
      />
      <button type="submit" disabled={createVideo.isPending}>
        {createVideo.isPending ? 'Adding...' : 'Add video'}
      </button>
      {createVideo.error && <p role="alert">{createVideo.error.message}</p>}
    </form>
  )
}
