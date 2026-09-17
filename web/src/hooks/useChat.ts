import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clearChatHistory, getChatHistory, sendChatMessage } from '../api/chat'

const chatKey = (videoId: string) => ['chat', videoId]

export function useChatHistoryQuery(videoId: string) {
  return useQuery({
    queryKey: chatKey(videoId),
    queryFn: () => getChatHistory(videoId),
  })
}

export function useSendChatMessage(videoId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (message: string) => sendChatMessage(videoId, message),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: chatKey(videoId) }),
  })
}

export function useClearChat(videoId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => clearChatHistory(videoId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: chatKey(videoId) }),
  })
}
