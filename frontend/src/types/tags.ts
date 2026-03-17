/**
 * Tags domain types.
 * Mirror the backend DTO shapes — keep in sync with backend/domains/tags/dto.py.
 */

export interface TagRulePattern {
  id: string
  pattern: string
  display_name: string
  category: string
  source: 'manual' | 'seed'
  added_at: string
  added_by: string
}

export interface TagRule {
  id: string
  tag_name: string
  description: string
  patterns: TagRulePattern[]
  apply_status: 'idle' | 'running' | 'done' | 'failed'
  last_applied_at: string | null
  last_applied_count: number
  created_at: string
  updated_at: string
  created_by: string
}

export interface TagPreviewAgent {
  source_id: string
  hostname: string
  group_name: string
  site_name: string
  os_type: string
  matched_patterns: string[]
  existing_tags: string[]
}

export interface TagPreviewResponse {
  rule_id: string
  tag_name: string
  matched_count: number
  preview_capped: boolean
  agents: TagPreviewAgent[]
}

export interface TagApplyResponse {
  status: 'started' | 'already_running'
  rule_id: string
}

export interface TagRuleCreateRequest {
  tag_name: string
  description?: string
}

export interface TagRuleUpdateRequest {
  tag_name?: string
  description?: string
}

export interface TagPatternCreateRequest {
  pattern: string
  display_name: string
  category: string
  source?: 'manual' | 'seed'
}

/** Source tag from the synced source_tags collection */
export interface SourceTag {
  source_id: string
  source: string
  name: string
  description: string | null
  type: string
  scope: string
  creator: string | null
  created_at: string | null
  updated_at: string | null
  synced_at: string
}

export interface SourceTagsResponse {
  tags: SourceTag[]
  total: number
}
