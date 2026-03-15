/**
 * Agent domain types.
 * Mirror the backend DTO shapes — keep in sync with backend/domains/sync/dto.py.
 */

export interface Agent {
  s1_agent_id: string
  hostname: string
  os_type: 'windows' | 'linux' | 'macos' | string
  os_version: string
  group_id: string
  group_name: string
  network_status: 'connected' | 'disconnected' | string
  last_active: string
  machine_type: 'desktop' | 'laptop' | 'server' | 'virtual' | string
  domain: string | null
  ip_addresses: string[]
  tags: string[]
  synced_at: string
}

export interface InstalledApplication {
  agent_id: string
  name: string
  normalized_name: string
  version: string | null
  publisher: string | null
  size: number | null
  installed_at: string | null
  synced_at: string
}

export interface AgentListResponse {
  agents: Agent[]
  total: number
  page: number
  limit: number
}

export interface AgentDetailResponse extends Agent {
  installed_apps: InstalledApplication[]
  classification?: import('./classification').ClassificationResult
}
