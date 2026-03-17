import client from './client'

export interface TopApp {
  normalized_name: string
  display_name: string
  agent_count: number
  coverage: number
}

export interface TopPublisher {
  publisher: string
  app_count: number
}

export interface FleetStats {
  total_agents: number
  total_groups: number
  total_sites: number
  agent_status: Record<string, number>
  os_distribution: Record<string, number>
  machine_type: Record<string, number>
  stale_7d: number
  stale_14d: number
  stale_30d: number
}

export interface AppStats {
  distinct_apps: number
  avg_apps_per_agent: number
  unique_apps: number
  top_apps: TopApp[]
  top_publishers: TopPublisher[]
  risk_distribution: Record<string, number>
}

export interface FingerprintingStats {
  total_groups: number
  groups_with_fingerprint: number
  groups_without_fingerprint: number
  thin_fingerprints: number
  avg_markers_per_fingerprint: number
  pending_proposals: number
}

export const getFleet = () =>
  client.get<FleetStats>('/dashboard/fleet').then((r) => r.data)

export const getApps = () =>
  client.get<AppStats>('/dashboard/apps').then((r) => r.data)

export const getFingerprinting = () =>
  client.get<FingerprintingStats>('/dashboard/fingerprinting').then((r) => r.data)
