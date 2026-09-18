export type QuestionType = 'multiple_choice' | 'multi_select' | 'true_false'
export type QuizScope = 'whole_video' | 'topics'
export type QuizDifficulty = 'easy' | 'medium' | 'hard' | 'mixed'

export interface QuizConfig {
  count: number
  scope: QuizScope
  segment_ids?: string[]
  question_types: QuestionType[]
  options_per_question?: number
  difficulty?: QuizDifficulty
  title?: string
}

// Options and questions carry no answer key: `is_correct` and `explanation` are only
// revealed in attempt results.
export interface QuizOption {
  id: string
  text: string
  order_index: number
}

export interface QuizQuestion {
  id: string
  order_index: number
  question_type: QuestionType
  prompt: string
  difficulty: string | null
  options: QuizOption[]
}

export interface Quiz {
  id: string
  video_id: string
  title: string
  config: Record<string, unknown>
  created_at: string
  questions: QuizQuestion[]
}

export interface QuizListItem {
  id: string
  video_id: string
  title: string
  config: Record<string, unknown>
  created_at: string
  question_count: number
  best_score: number | null
}

export interface AnswerIn {
  question_id: string
  selected_option_ids: string[]
}

export interface AttemptIn {
  answers: AnswerIn[]
}

export interface QuestionResult {
  question_id: string
  is_correct: boolean
  selected_option_ids: string[]
  correct_option_ids: string[]
  explanation: string
  segment_id: string | null
  source_start_time: number | null
}

export interface AttemptResult {
  attempt_id: string
  score: number
  results: QuestionResult[]
}

export interface AttemptListItem {
  id: string
  score: number
  correct_count: number
  question_count: number
  started_at: string
  completed_at: string | null
}
