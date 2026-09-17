import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createVideo, deleteVideo, getVideo, listVideos, reprocessVideo } from '../api/videos'
import type { VideoDetail, VideoListItem } from '../types/video'

const VIDEOS_KEY = ['videos']
const videoKey = (id: string) => ['videos', id]

function isInProgress(video: { status: string } | undefined): boolean {
  return video?.status === 'pending' || video?.status === 'processing'
}

export function useVideosQuery() {
  return useQuery({
    queryKey: VIDEOS_KEY,
    queryFn: listVideos,
    refetchInterval: (query) =>
      (query.state.data as VideoListItem[] | undefined)?.some(isInProgress) ? 1500 : false,
  })
}

export function useVideoQuery(id: string) {
  return useQuery({
    queryKey: videoKey(id),
    queryFn: () => getVideo(id),
    refetchInterval: (query) => (isInProgress(query.state.data as VideoDetail | undefined) ? 1500 : false),
  })
}

export function useReprocessVideo(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => reprocessVideo(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: videoKey(id) }),
  })
}

export function useCreateVideo() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createVideo,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: VIDEOS_KEY }),
  })
}

export function useDeleteVideo() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteVideo,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: VIDEOS_KEY }),
  })
}
