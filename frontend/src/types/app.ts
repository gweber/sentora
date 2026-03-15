/**
 * App domain types.
 *
 * Mirror the DTOs in ``domains/agents/apps_router.py``.
 */

export interface AppListItem {
  normalized_name: string
  display_name: string
  publisher: string | null
  agent_count: number
  category: string | null
  category_display: string | null
}

export interface AppListResponse {
  apps: AppListItem[]
  total: number
  page: number
  limit: number
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
  agents: AppAgentRow[]
  taxonomy_match: AppTaxonomyMatch | null
}
