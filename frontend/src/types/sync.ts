/**
 * Sync domain types.
 * Mirror the backend DTO shapes — keep in sync with backend/domains/sync/dto.py.
 */

export type SyncStatus = 'running' | 'completed' | 'failed' | 'interrupted'
export type SyncTrigger = 'manual' | 'scheduled' | 'phase' | 'refresh' | 'resume'
export type SyncMode = 'full' | 'incremental' | 'auto'
export type SyncPhase = 'sites' | 'groups' | 'agents' | 'apps' | 'tags'
  | 'cs_groups' | 'cs_agents' | 'cs_apps'
  | 'done' | null

/** Supported data sources. */
export type SyncSource = 'sentinelone' | 'crowdstrike'

export interface SyncCounts {
  sites_synced: number
  sites_total: number
  groups_synced: number
  groups_total: number
  agents_synced: number
  agents_total: number
  apps_synced: number
  apps_total: number
  tags_synced: number
  tags_total: number
  errors: number
}

export interface SyncRun {
  id: string
  started_at: string
  completed_at: string | null
  status: SyncStatus
  trigger: SyncTrigger
  mode: SyncMode
  counts: SyncCounts
  phase: SyncPhase
  message: string | null
}

export interface SyncTriggerRequest {
  mode: SyncMode
  phases?: string[]
  source?: SyncSource
}

export interface SyncDbCounts {
  agents: number
  groups: number
  sites: number
  apps: number
  tags: number
}

export interface PhaseSchedule {
  interval_minutes: number
  last_synced_at: string | null
  next_run_at: string | null
}

export interface SyncStatusResponse {
  current_run: SyncRun | null
  last_completed_run: SyncRun | null
  db_counts: SyncDbCounts | null
  schedule?: Record<string, PhaseSchedule>
}

export interface SyncHistoryResponse {
  runs: SyncRun[]
  total: number
}

/** Per-phase progress snapshot sent from the backend. */
export interface PhaseProgress {
  status: 'idle' | 'running' | 'completed' | 'failed' | 'cancelled'
  synced: number
  total: number
  message?: string | null
}

/** WebSocket message shape for live sync progress */
export interface SyncProgressMessage {
  type: 'progress' | 'completed' | 'failed' | 'ping'
  run_id: string
  status: SyncStatus
  phase: SyncPhase
  counts: SyncCounts
  message?: string
  phase_details?: Record<string, PhaseProgress>
}
