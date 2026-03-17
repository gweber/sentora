/**
 * App domain types.
 *
 * Mirror the DTOs in ``domains/agents/apps_router.py``.
 */

export interface AppEolInfo {
  eol_product_id: string
  match_source: string
  match_confidence: number
}

export interface AppListItem {
  normalized_name: string
  display_name: string
  publisher: string | null
  agent_count: number
  category: string | null
  category_display: string | null
  eol: AppEolInfo | null
}

export interface AppListResponse {
  apps: AppListItem[]
  total: number
  page: number
  limit: number
  /** Total known (categorized) apps across all pages. May be absent on older APIs. */
  known_count?: number
  /** Total unknown (uncategorized) apps across all pages. May be absent on older APIs. */
  unknown_count?: number
}

export interface AppVersionRow {
  version: string
  count: number
}

export interface AppAgentRow {
  agent_id: string
  hostname: string
  group_id: string
  group_name: string
  site_id: string
  site_name: string
  os_type: string
  version: string | null
  installed_at: string | null
  last_active: string | null
}

export interface AppTaxonomyMatch {
  name: string
  category: string
  subcategory: string | null
  publisher: string | null
  is_universal: boolean
}

export interface NameCountRow {
  name: string
  count: number
}

export interface AppVersionEolStatus {
  version: string
  agent_count: number
  cycle: string | null
  is_eol: boolean
  eol_date: string | null
  is_security_only: boolean
  support_end: string | null
}

export interface AppEolDetail {
  eol_product_id: string
  product_name: string
  match_source: string
  match_confidence: number
  versions: AppVersionEolStatus[]
}

export interface AppStats {
  normalized_name: string
  display_name: string
  publisher: string | null
  risk_level: string | null
  agent_count: number
  group_count: number
  site_count: number
  versions: AppVersionRow[]
  risk_distribution: Record<string, number>
  group_breakdown: NameCountRow[]
  site_breakdown: NameCountRow[]
  taxonomy_match: AppTaxonomyMatch | null
  eol: AppEolDetail | null
}

export interface AppAgentsResponse {
  agents: AppAgentRow[]
  total: number
  page: number
  page_size: number
}

/** @deprecated Use AppStats + AppAgentsResponse instead. */
export interface AppDetail {
  normalized_name: string
  display_name: string
  publisher: string | null
  risk_level: string | null
  agent_count: number
  group_count: number
  site_count: number
  versions: AppVersionRow[]
  risk_distribution: Record<string, number>
  group_breakdown: NameCountRow[]
  site_breakdown: NameCountRow[]
  agents: AppAgentRow[]
  taxonomy_match: AppTaxonomyMatch | null
  eol: AppEolDetail | null
  page: number
  page_size: number
  filtered_agent_count: number | null
}
