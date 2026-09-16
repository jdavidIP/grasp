import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createVideo, deleteVideo, listVideos } from '../api/videos'
import type { VideoListItem } from '../types/video'

const VIDEOS_KEY = ['videos']

function isInProgress(videos: VideoListItem[] | undefined): boolean {
  return videos?.some((v) => v.status === 'pending' || v.status === 'processing') ?? false
}

export function useVideosQuery() {
  return useQuery({
    queryKey: VIDEOS_KEY,
    queryFn: listVideos,
    refetchInterval: (query) => (isInProgress(query.state.data) ? 1500 : false),
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
