import { useEffect, useRef } from 'react'
import './YouTubePlayer.css'

interface YouTubePlayerInstance {
  seekTo(seconds: number, allowSeekAhead: boolean): void
  playVideo(): void
  destroy(): void
}

interface YouTubeIframeApi {
  Player: new (
    element: HTMLElement,
    options: {
      videoId: string
      width?: string
      height?: string
      playerVars?: Record<string, number>
    },
  ) => YouTubePlayerInstance
}

declare global {
  interface Window {
    YT?: YouTubeIframeApi
    onYouTubeIframeAPIReady?: () => void
  }
}

let apiLoadPromise: Promise<void> | null = null

function loadYouTubeApi(): Promise<void> {
  if (apiLoadPromise) return apiLoadPromise
  apiLoadPromise = new Promise((resolve) => {
    if (window.YT) {
      resolve()
      return
    }
    const previous = window.onYouTubeIframeAPIReady
    window.onYouTubeIframeAPIReady = () => {
      previous?.()
      resolve()
    }
    const script = document.createElement('script')
    script.src = 'https://www.youtube.com/iframe_api'
    document.head.appendChild(script)
  })
  return apiLoadPromise
}

// A new object per click, so seeking to the same time twice still seeks.
export interface SeekRequest {
  seconds: number
  id: number
}

interface YouTubePlayerProps {
  videoId: string
  // null means "nothing sought yet", distinct from a real 0:00 timestamp.
  seek: SeekRequest | null
}

export function YouTubePlayer({ videoId, seek }: YouTubePlayerProps) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const playerRef = useRef<YouTubePlayerInstance | null>(null)

  useEffect(() => {
    let cancelled = false
    // The YouTube IFrame API replaces its target element with an <iframe> — a DOM
    // mutation React never sees. Handing it containerRef.current directly (the node
    // React itself renders) corrupts React's reconciliation the next time this
    // component unmounts: React tries to remove a node that's no longer there,
    // throwing "Failed to execute 'insertBefore'" and taking the whole app down with
    // it (no error boundary catches it). Issue #25, hit via Reprocess.
    //
    // Fix: give the API a target div created outside React's tree entirely (never
    // JSX, never reconciled). React only ever owns the wrapper, whose children it
    // never inspects, so removing it on unmount is always safe regardless of what
    // the YouTube API did to its insides.
    const wrapper = wrapperRef.current
    const target = document.createElement('div')
    wrapper?.appendChild(target)

    loadYouTubeApi().then(() => {
      if (cancelled || !window.YT) return
      playerRef.current = new window.YT.Player(target, {
        videoId,
        width: '100%',
        height: '100%',
        playerVars: { autoplay: 1 },
      })
    })
    return () => {
      cancelled = true
      playerRef.current?.destroy()
      playerRef.current = null
      // Remove whatever this run left in the wrapper (the target, or the iframe the API
      // swapped in for it), so a re-run or a new video doesn't stack a second player.
      // React renders no children into the wrapper, so emptying it is safe.
      wrapper?.replaceChildren()
    }
  }, [videoId])

  useEffect(() => {
    if (seek === null) return
    playerRef.current?.seekTo(seek.seconds, true)
    playerRef.current?.playVideo()
  }, [seek])

  return <div ref={wrapperRef} className="youtube-player" />
}
