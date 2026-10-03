import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router'
import { AppHeader } from '../components/AppHeader'
import { ChatPanel } from '../components/ChatPanel'
import { Corners } from '../components/Corners'
import { FlashcardsPanel } from '../components/FlashcardsPanel'
import { QuizzesPanel } from '../components/QuizzesPanel'
import { TopicList } from '../components/TopicList'
import { WorkspaceTabs } from '../components/WorkspaceTabs'
import { YouTubePlayer, type SeekRequest } from '../components/YouTubePlayer'
import { useReprocessVideo, useVideoQuery } from '../hooks/useVideos'
import { STATUS_TAG, plural } from '../lib/format'
import { formatTime } from '../lib/time'
import { useToast } from '../lib/toast'
import './VideoDetailPage.css'

export function VideoDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: video, isLoading, error } = useVideoQuery(id!)
  const reprocess = useReprocessVideo(id!)
  const toast = useToast()
  const [seekRequest, setSeekRequest] = useState<SeekRequest | null>(null)

  const seek = useCallback(
    (seconds: number) => {
      setSeekRequest((previous) => ({ seconds, id: (previous?.id ?? 0) + 1 }))
      toast(`Jumped to ${formatTime(seconds)}`)
    },
    [toast],
  )

  const inProgress = video?.status === 'pending' || video?.status === 'processing'
  const meta = video
    ? [
        video.channel,
        video.duration_seconds !== null ? formatTime(video.duration_seconds) : null,
        plural(video.segments.length, 'segment'),
      ]
        .filter(Boolean)
        .join(' · ')
    : ''

  return (
    <>
      <AppHeader meta={video?.youtube_id ?? ''} />
      <main className="workspace">
        <Link to="/" className="btn btn-secondary workspace-back">
          ← Library
        </Link>
        {isLoading && <p className="text-muted">Loading…</p>}
        {error && (
          <p role="alert" className="workspace-error">
            {error.message}
          </p>
        )}
        {video && (
          <div className="workspace-columns">
            <div className="workspace-left">
              <div className="workspace-title-row">
                <div className="workspace-title">
                  <h2>{video.title}</h2>
                  <span className="text-muted tabular workspace-meta">{meta}</span>
                </div>
                <div className="workspace-title-actions">
                  <span className={`tag ${STATUS_TAG[video.status]} workspace-tag`}>{video.status}</span>
                  {!inProgress && (
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => {
                        if (
                          window.confirm(
                            "Reprocessing rebuilds this video's topics and deletes its chat history. Continue?",
                          )
                        )
                          reprocess.mutate()
                      }}
                      disabled={reprocess.isPending}
                    >
                      Reprocess
                    </button>
                  )}
                </div>
              </div>
              {reprocess.isError && (
                <p role="alert" className="workspace-error">
                  {reprocess.error.message}
                </p>
              )}
              {video.status === 'failed' && video.error_message && (
                <p role="alert" className="workspace-error">
                  {video.error_message}
                </p>
              )}

              {video.status === 'ready' && (
                <figure className="blueprint workspace-player">
                  <Corners />
                  <YouTubePlayer videoId={video.youtube_id} seek={seekRequest} />
                </figure>
              )}

              <TopicList segments={video.segments} onSeek={seek} />
            </div>

            <div className="workspace-right">
              {video.status === 'ready' ? (
                <WorkspaceTabs
                  chat={<ChatPanel videoId={video.id} onSeek={seek} />}
                  flashcards={<FlashcardsPanel videoId={video.id} segments={video.segments} onSeek={seek} />}
                  quizzes={<QuizzesPanel videoId={video.id} segments={video.segments} onSeek={seek} />}
                />
              ) : (
                <div className="blueprint workspace-unavailable">
                  <Corners />
                  <p className="text-muted">
                    {video.status === 'failed'
                      ? "This video couldn't be processed. Reprocess it to use chat, flashcards and quizzes."
                      : 'Chat, flashcards and quizzes open once the video is processed.'}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </>
  )
}
