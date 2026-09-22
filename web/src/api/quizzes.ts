import { apiFetch } from './client'
import type {
  AttemptIn,
  AttemptListItem,
  AttemptResult,
  Quiz,
  QuizConfig,
  QuizListItem,
} from '../types/quiz'

export function listQuizzes(videoId: string): Promise<QuizListItem[]> {
  return apiFetch(`/videos/${videoId}/quizzes`)
}

export function createQuiz(videoId: string, config: QuizConfig): Promise<Quiz> {
  return apiFetch(`/videos/${videoId}/quizzes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
}

export function getQuiz(quizId: string): Promise<Quiz> {
  return apiFetch(`/quizzes/${quizId}`)
}

export function deleteQuiz(quizId: string): Promise<void> {
  return apiFetch(`/quizzes/${quizId}`, { method: 'DELETE' })
}

export function submitAttempt(quizId: string, attempt: AttemptIn): Promise<AttemptResult> {
  return apiFetch(`/quizzes/${quizId}/attempts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(attempt),
  })
}

export function listAttempts(quizId: string): Promise<AttemptListItem[]> {
  return apiFetch(`/quizzes/${quizId}/attempts`)
}

export function getAttempt(quizId: string, attemptId: string): Promise<AttemptResult> {
  return apiFetch(`/quizzes/${quizId}/attempts/${attemptId}`)
}
