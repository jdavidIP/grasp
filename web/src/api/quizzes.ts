import { API_URL, handleResponse } from './client'
import type {
  AttemptIn,
  AttemptListItem,
  AttemptResult,
  Quiz,
  QuizConfig,
  QuizListItem,
} from '../types/quiz'

export function listQuizzes(videoId: string): Promise<QuizListItem[]> {
  return fetch(`${API_URL}/videos/${videoId}/quizzes`).then((res) => handleResponse(res))
}

export function createQuiz(videoId: string, config: QuizConfig): Promise<Quiz> {
  return fetch(`${API_URL}/videos/${videoId}/quizzes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  }).then((res) => handleResponse(res))
}

export function getQuiz(quizId: string): Promise<Quiz> {
  return fetch(`${API_URL}/quizzes/${quizId}`).then((res) => handleResponse(res))
}

export function deleteQuiz(quizId: string): Promise<void> {
  return fetch(`${API_URL}/quizzes/${quizId}`, { method: 'DELETE' }).then((res) =>
    handleResponse(res),
  )
}

export function submitAttempt(quizId: string, attempt: AttemptIn): Promise<AttemptResult> {
  return fetch(`${API_URL}/quizzes/${quizId}/attempts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(attempt),
  }).then((res) => handleResponse(res))
}

export function listAttempts(quizId: string): Promise<AttemptListItem[]> {
  return fetch(`${API_URL}/quizzes/${quizId}/attempts`).then((res) => handleResponse(res))
}

export function getAttempt(quizId: string, attemptId: string): Promise<AttemptResult> {
  return fetch(`${API_URL}/quizzes/${quizId}/attempts/${attemptId}`).then((res) =>
    handleResponse(res),
  )
}
