/**
 * Classification domain types.
 * Mirror the backend DTO shapes — keep in sync with backend/domains/classification/dto.py.
 */

export type ClassificationVerdict = 'correct' | 'misclassified' | 'ambiguous' | 'unclassifiable'

export interface GroupMatchScore {
  group_id: string
  group_name: string
  score: number
  matched_markers: string[]
  missing_markers: string[]
}

export interface ClassificationResult {
  agent_id: string
  hostname: string
  current_group_id: string
  current_group_name: string
  match_scores: GroupMatchScore[]
  classification: ClassificationVerdict
  suggested_group_id: string | null
  suggested_group_name: string | null
  anomaly_reasons: string[]
  ml_score: number | null
  ml_verdict: string | null
  anomaly_score: number | null
  anomaly_flag: boolean
  computed_at: string
  acknowledged?: boolean
}

export interface ClassificationOverview {
  total: number
  correct: number
  misclassified: number
  ambiguous: number
  unclassifiable: number
  groups_count: number
  last_computed_at: string | null
}

export interface ClassificationResultListResponse {
  results: ClassificationResult[]
  total: number
  page: number
  limit: number
}
