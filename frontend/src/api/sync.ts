/**
 * Sync domain API calls.
 */

import type {
  SyncHistoryResponse,
  SyncStatusResponse,
  SyncTriggerRequest,
} from '@/types/sync'
import client from './client'

/** Trigger all (or selected) phases independently. */
export async function triggerSync(payload: SyncTriggerRequest): Promise<Record<string, unknown>> {
  const { data } = await client.post('/sync/trigger', payload)
  return data
}

/** Trigger an incremental refresh of all phases. */
export async function triggerRefresh(): Promise<Record<string, unknown>> {
  const { data } = await client.post('/sync/refresh')
  return data
}

/** Get the current (or last) sync status. */
export async function getSyncStatus(): Promise<SyncStatusResponse> {
  const { data } = await client.get<SyncStatusResponse>('/sync/status')
  return data
}

/** Get paginated sync run history. */
export async function getSyncHistory(page = 1, limit = 20): Promise<SyncHistoryResponse> {
  const { data } = await client.get<SyncHistoryResponse>('/sync/history', {
    params: { page, limit },
  })
  return data
}

/** Cancel the currently running sync (cooperative — stops at next checkpoint). */
export async function cancelSync(): Promise<void> {
  await client.post('/sync/cancel')
}

/** Backfill installed_app_names onto all s1_agents documents (one-time migration). */
export async function backfillAppNames(): Promise<void> {
  await client.post('/sync/backfill-app-names')
}

/** Re-normalize all app names (strip version suffixes) then rebuild installed_app_names. */
export async function renormalizeApps(): Promise<void> {
  await client.post('/sync/renormalize-apps')
}

// ── Per-phase endpoints ──────────────────────────────────────────────────────

/** Trigger a single phase independently. */
export async function triggerPhase(phase: string, mode = 'auto'): Promise<Record<string, unknown>> {
  const { data } = await client.post(`/sync/phase/${phase}/trigger`, { mode })
  return data
}
