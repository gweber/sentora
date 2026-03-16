/**
 * Fingerprint domain types.
 * Mirror the backend DTO shapes — keep in sync with backend/domains/fingerprint/dto.py.
 */

export interface FingerprintMarker {
  id: string
  pattern: string
  display_name: string
  category: string
  weight: number
  source: 'manual' | 'statistical' | 'seed'
  confidence: number
  added_at: string
  added_by: string
}

export interface Fingerprint {
  id: string
  group_id: string
  group_name: string
  site_name: string
  account_name: string
  markers: FingerprintMarker[]
  created_at: string
  updated_at: string
  created_by: string
}

export interface FingerprintSuggestion {
  id: string
  group_id: string
  normalized_name: string
  display_name: string
  score: number
  group_coverage: number
  outside_coverage: number
  agent_count_in_group: number
  agent_count_outside: number
  status: 'pending' | 'accepted' | 'rejected'
  computed_at: string
}

export interface MarkerCreateRequest {
  pattern: string
  display_name: string
  category: string
  weight?: number
  source?: 'manual' | 'statistical' | 'seed'
}

export interface MarkerUpdateRequest {
  weight?: number
  pattern?: string
  display_name?: string
}

// ── Auto-fingerprint proposals ────────────────────────────────────────────────

export interface ProposedMarker {
  normalized_name: string
  display_name: string
  /** Lift statistic — "12" means agents in this group are 12× more likely to have the app. */
  lift: number
  /** Fraction of group agents that have this app (0–1). */
  group_coverage: number
  /** Fraction of non-group agents that have this app (0–1). */
  outside_coverage: number
  agent_count_in_group: number
  agent_count_outside: number
  /** Group IDs of other groups that also propose this same app. */
  shared_with_groups: string[]
}

export interface AutoFingerprintProposal {
  id: string
  group_id: string
  group_name: string
  group_size: number
  proposed_markers: ProposedMarker[]
  /** Mean lift across all proposed markers. */
  quality_score: number
  total_groups: number
  coverage_min: number
  outside_max: number
  lift_min: number
  top_k: number
  status: 'pending' | 'applied' | 'dismissed'
  computed_at: string
}

export interface ApplyProposalResult {
  added: number
  skipped: number
  status: 'applied'
}

// ── Import / Export ──────────────────────────────────────────────────────────

export interface FingerprintExportMarker {
  pattern: string
  display_name: string
  category: string
  weight: number
  source: 'manual' | 'statistical' | 'seed'
  confidence: number
}

export interface FingerprintExportItem {
  group_id: string
  markers: FingerprintExportMarker[]
}

export interface FingerprintImportResponse {
  imported: number
  skipped: number
  errors: string[]
}
