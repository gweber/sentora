/** Persisted application configuration returned by GET /api/v1/config/ */
export interface AppConfig {
  classification_threshold: number
  partial_threshold: number
  ambiguity_gap: number
  universal_app_threshold: number
  suggestion_score_threshold: number
  page_size_agents: number
  page_size_apps: number
  page_size_audit: number
  refresh_interval_minutes: number
  schedule_sites_minutes: number
  schedule_groups_minutes: number
  schedule_agents_minutes: number
  schedule_apps_minutes: number
  schedule_tags_minutes: number
  proposal_coverage_min: number
  proposal_outside_max: number
  proposal_lift_min: number
  proposal_top_k: number
  brand_app_name: string
  brand_tagline: string
  brand_primary_color: string
  brand_logo_url: string
  brand_favicon_url: string
  nvd_api_key_set: boolean
  session_max_lifetime_days: number
  session_inactivity_timeout_days: number
  account_lockout_threshold: number
  account_lockout_duration_minutes: number
  password_min_length: number
  password_require_uppercase: boolean
  password_require_lowercase: boolean
  password_require_digit: boolean
  password_require_special: boolean
  password_history_count: number
  password_max_age_days: number
  password_check_breached: boolean
  updated_at: string
}

/** Partial update payload for PUT /api/v1/config/ */
export interface AppConfigUpdate {
  classification_threshold?: number
  partial_threshold?: number
  ambiguity_gap?: number
  universal_app_threshold?: number
  suggestion_score_threshold?: number
  page_size_agents?: number
  page_size_apps?: number
  page_size_audit?: number
  refresh_interval_minutes?: number
  schedule_sites_minutes?: number
  schedule_groups_minutes?: number
  schedule_agents_minutes?: number
  schedule_apps_minutes?: number
  schedule_tags_minutes?: number
  proposal_coverage_min?: number
  proposal_outside_max?: number
  proposal_lift_min?: number
  proposal_top_k?: number
  brand_app_name?: string
  brand_tagline?: string
  brand_primary_color?: string
  brand_logo_url?: string
  brand_favicon_url?: string
  nvd_api_key?: string
  session_max_lifetime_days?: number
  session_inactivity_timeout_days?: number
  account_lockout_threshold?: number
  account_lockout_duration_minutes?: number
  password_min_length?: number
  password_require_uppercase?: boolean
  password_require_lowercase?: boolean
  password_require_digit?: boolean
  password_require_special?: boolean
  password_history_count?: number
  password_max_age_days?: number
  password_check_breached?: boolean
}

/** Public branding info returned by GET /api/v1/branding (no auth required) */
export interface Branding {
  app_name: string
  tagline: string
  primary_color: string
  logo_url: string
  favicon_url: string
}
