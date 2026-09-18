import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createQuiz,
  deleteQuiz,
  getAttempt,
  getQuiz,
  listAttempts,
  listQuizzes,
  submitAttempt,
} from '../api/quizzes'
import type { AttemptIn, QuizConfig } from '../types/quiz'

const quizzesKey = (videoId: string) => ['quizzes', videoId]
const quizKey = (quizId: string) => ['quiz', quizId]
const attemptsKey = (quizId: string) => ['quiz-attempts', quizId]
const attemptKey = (quizId: string, attemptId: string) => ['quiz-attempt', quizId, attemptId]

export function useQuizzesQuery(videoId: string) {
  return useQuery({
    queryKey: quizzesKey(videoId),
    queryFn: () => listQuizzes(videoId),
  })
}

export function useQuizQuery(quizId: string) {
  return useQuery({
    queryKey: quizKey(quizId),
    queryFn: () => getQuiz(quizId),
  })
}

export function useCreateQuiz(videoId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (config: QuizConfig) => createQuiz(videoId, config),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quizzesKey(videoId) }),
  })
}

export function useDeleteQuiz(videoId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (quizId: string) => deleteQuiz(quizId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quizzesKey(videoId) }),
  })
}

export function useSubmitAttempt(videoId: string, quizId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (attempt: AttemptIn) => submitAttempt(quizId, attempt),
    onSuccess: () => {
      // A new attempt can change the quiz's best score and adds to its history.
      queryClient.invalidateQueries({ queryKey: quizzesKey(videoId) })
      queryClient.invalidateQueries({ queryKey: attemptsKey(quizId) })
    },
  })
}

export function useAttemptsQuery(quizId: string) {
  return useQuery({
    queryKey: attemptsKey(quizId),
    queryFn: () => listAttempts(quizId),
  })
}

export function useAttemptQuery(quizId: string, attemptId: string) {
  return useQuery({
    queryKey: attemptKey(quizId, attemptId),
    queryFn: () => getAttempt(quizId, attemptId),
  })
}
