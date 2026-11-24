export type Preferences = { role: string; topic: string; difficulty: string; question_count: number }
export type Feedback = {
  technical_accuracy: number; completeness: number; clarity: number; reasoning: number; score: number
  strengths: string[]; missing_concepts: string[]; suggestions: string[]
}
export type Turn = { question_number: number; question: string; answer: string; feedback: Feedback }
export type Session = Preferences & {
  id: string; created_at: string; question_number: number; question: string; model: string
  status: 'awaiting_answer' | 'feedback' | 'completed'; history: Turn[]
  summary: { answered: number; overall_score: number; category_scores: Record<string, number>; suggestions: string[] } | null
}
