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
  const containerRef = useRef<HTMLDivElement>(null)
  const playerRef = useRef<YouTubePlayerInstance | null>(null)

  useEffect(() => {
    let cancelled = false
    loadYouTubeApi().then(() => {
      if (cancelled || !containerRef.current || !window.YT) return
      playerRef.current = new window.YT.Player(containerRef.current, {
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

  return <div ref={containerRef} />
}
