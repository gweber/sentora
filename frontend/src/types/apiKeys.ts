/** API Keys domain types. */

export interface APIKeyResponse {
  id: string
  tenant_id: string
  name: string
  description: string | null
  key_prefix: string
  scopes: string[]
  rate_limit_per_minute: number
  rate_limit_per_hour: number
  created_at: string
  created_by: string
  expires_at: string | null
  last_used_at: string | null
  last_used_ip: string | null
  is_active: boolean
  revoked_at: string | null
  revoked_by: string | null
}

export interface APIKeyCreateRequest {
  name: string
  description?: string
  scopes: string[]
  rate_limit_per_minute?: number
  rate_limit_per_hour?: number
  expires_at?: string
}

export interface APIKeyUpdateRequest {
  name?: string
  description?: string
  scopes?: string[]
  rate_limit_per_minute?: number
  rate_limit_per_hour?: number
  expires_at?: string
}

export interface APIKeyCreateResponse {
  key: APIKeyResponse
  full_key: string
}

export interface APIKeyRotateResponse {
  key: APIKeyResponse
  full_key: string
}

export interface APIKeyCurrentResponse {
  id: string
  name: string
  key_prefix: string
  scopes: string[]
  rate_limit_per_minute: number
  rate_limit_per_hour: number
  last_used_at: string | null
}

/** Available scope definitions for the UI. */
export const AVAILABLE_SCOPES: Record<string, string> = {
  // Read-only
  'agents:read': 'List and view agents',
  'apps:read': 'List and view installed applications',
  'compliance:read': 'View compliance results and violations',
  'enforcement:read': 'View enforcement rules and violations',
  'audit:read': 'View audit log entries',
  'sync:read': 'View sync status and history',
  'taxonomy:read': 'View taxonomy categories',
  'fingerprints:read': 'View fingerprints',
  'dashboard:read': 'View dashboard metrics',
  // Write
  'sync:trigger': 'Trigger a manual sync',
  'enforcement:write': 'Create and modify enforcement rules',
  'tags:write': 'Create and assign tags',
  // Convenience
  'read:all': 'All read-only scopes',
  'write:all': 'All write scopes (implies read:all)',
}

export const READ_SCOPES = Object.keys(AVAILABLE_SCOPES).filter(s => s.endsWith(':read'))
export const WRITE_SCOPES = Object.keys(AVAILABLE_SCOPES).filter(
  s => !s.endsWith(':read') && s !== 'read:all' && s !== 'write:all',
)
