/**
 * Taxonomy domain types.
 * Mirror the backend DTO shapes — keep in sync with backend/domains/taxonomy/dto.py.
 */

export interface SoftwareEntry {
  id: string
  name: string
  patterns: string[]
  publisher: string | null
  category: string
  category_display: string
  subcategory: string | null
  industry: string[]
  description: string | null
  is_universal: boolean
  user_added: boolean
  created_at: string
  updated_at: string
}

export interface CategorySummary {
  key: string
  display: string
  entry_count: number
}

export interface CategoryListResponse {
  categories: CategorySummary[]
  total: number
}

export interface SoftwareEntryListResponse {
  entries: SoftwareEntry[]
  total: number
}

export interface SoftwareEntryCreateRequest {
  name: string
  patterns: string[]
  publisher?: string | null
  category: string
  category_display?: string
  subcategory?: string | null
  industry?: string[]
  description?: string | null
  is_universal?: boolean
}

export interface SoftwareEntryUpdateRequest {
  name?: string
  patterns?: string[]
  publisher?: string | null
  category?: string
  category_display?: string
  subcategory?: string | null
  industry?: string[]
  description?: string | null
  is_universal?: boolean
}

export interface PatternPreviewRequest {
  pattern?: string
  patterns?: string[]
}

export interface AppMatch {
  normalized_name: string
  display_name: string
  publisher: string | null
  agent_count: number
}

export interface GroupCount {
  group_name: string
  agent_count: number
}

export interface PatternPreviewResponse {
  patterns: string[]
  total_apps: number
  total_agents: number
  app_matches: AppMatch[]
  group_counts: GroupCount[]
}

export interface CategoryCreateRequest {
  key: string
  display: string
}

export interface CategoryUpdateRequest {
  key?: string
  display?: string
}

export interface CategoryUpdateResponse {
  old_key: string
  new_key: string
  display: string
  entries_updated: number
}

export interface CategoryDeleteResponse {
  key: string
  entries_deleted: number
}
