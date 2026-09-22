import { useEffect, useRef } from 'react'

interface YouTubePlayerInstance {
  seekTo(seconds: number, allowSeekAhead: boolean): void
  playVideo(): void
  destroy(): void
}

interface YouTubeIframeApi {
  Player: new (
    element: HTMLElement,
    options: { videoId: string; playerVars?: Record<string, number> },
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

interface YouTubePlayerProps {
  videoId: string
  // null means "no citation clicked yet" — distinct from a real 0:00 timestamp.
  seekSeconds: number | null
}

export function YouTubePlayer({ videoId, seekSeconds }: YouTubePlayerProps) {
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
    const target = document.createElement('div')
    wrapperRef.current?.appendChild(target)

    loadYouTubeApi().then(() => {
      if (cancelled || !window.YT) return
      playerRef.current = new window.YT.Player(target, {
        videoId,
        playerVars: { autoplay: 1 },
      })
    })
    return () => {
      cancelled = true
      playerRef.current?.destroy()
      playerRef.current = null
    }
  }, [videoId])

  useEffect(() => {
    if (seekSeconds === null) return
    playerRef.current?.seekTo(seekSeconds, true)
    playerRef.current?.playVideo()
  }, [seekSeconds])

  return <div ref={wrapperRef} />
}
