/**
 * Fingerprint Library API — browse, subscribe, and manage shared fingerprint entries.
 */

import client from './client'
import type {
  IngestionRunResponse,
  LibraryEntry,
  LibraryEntryCreateRequest,
  LibraryEntryListResponse,
  LibraryEntryUpdateRequest,
  LibraryStatsResponse,
  SourceInfo,
  SubscriptionListResponse,
  SubscriptionResponse,
} from '@/types/library'

/** List library entries with optional filters and pagination. */
export async function listEntries(params?: {
  status?: string
  source?: string
  category?: string
  search?: string
  page?: number
  page_size?: number
}): Promise<LibraryEntryListResponse> {
  const { data } = await client.get<LibraryEntryListResponse>('/library/', { params })
  return data
}

/** Get a single library entry by ID. */
export async function getEntry(id: string): Promise<LibraryEntry> {
  const { data } = await client.get<LibraryEntry>(`/library/entries/${id}`)
  return data
}

/** Create a new library entry. */
export async function createEntry(payload: LibraryEntryCreateRequest): Promise<LibraryEntry> {
  const { data } = await client.post<LibraryEntry>('/library/', payload)
  return data
}

/** Update a library entry. */
export async function updateEntry(id: string, payload: LibraryEntryUpdateRequest): Promise<LibraryEntry> {
  const { data } = await client.patch<LibraryEntry>(`/library/entries/${id}`, payload)
  return data
}

/** Delete a library entry. */
export async function deleteEntry(id: string): Promise<void> {
  await client.delete(`/library/entries/${id}`)
}

/** Publish a draft library entry. */
export async function publishEntry(id: string): Promise<LibraryEntry> {
  const { data } = await client.post<LibraryEntry>(`/library/entries/${id}/publish`)
  return data
}

/** Deprecate a library entry. */
export async function deprecateEntry(id: string): Promise<LibraryEntry> {
  const { data } = await client.post<LibraryEntry>(`/library/entries/${id}/deprecate`)
  return data
}

/** Preview what promoting a library entry to taxonomy would do. */
export async function promotePreview(id: string): Promise<{
  name: string
  vendor: string
  source: string
  category: string
  category_display: string
  patterns: string[]
  new_patterns: string[]
  would_merge: boolean
  existing_entry_name: string | null
  available_categories: { key: string; display: string }[]
}> {
  const { data } = await client.get(`/library/entries/${id}/promote-preview`)
  return data
}

/** Promote a library entry to the taxonomy catalog. */
export async function promoteToTaxonomy(id: string, category?: string): Promise<{
  taxonomy_entry_id: string
  name: string
  patterns_added: number
  created: boolean
}> {
  const { data } = await client.post(`/library/entries/${id}/promote-to-taxonomy`, {
    category: category || null,
  })
  return data
}

/** Subscribe a group to a library entry. */
export async function subscribeGroup(
  entryId: string,
  groupId: string,
  autoUpdate = true,
): Promise<SubscriptionResponse> {
  const { data } = await client.post<SubscriptionResponse>(
    `/library/entries/${entryId}/subscribe`,
    { group_id: groupId, auto_update: autoUpdate },
  )
  return data
}

/** Unsubscribe a group from a library entry. */
export async function unsubscribeGroup(entryId: string, groupId: string): Promise<void> {
  await client.delete(`/library/entries/${entryId}/subscribe/${groupId}`)
}

/** List all subscriptions for a group. */
export async function listGroupSubscriptions(groupId: string): Promise<SubscriptionListResponse> {
  const { data } = await client.get<SubscriptionListResponse>(`/library/subscriptions/group/${groupId}`)
  return data
}

/** List available ingestion sources. */
export async function listSources(): Promise<{ sources: SourceInfo[] }> {
  const { data } = await client.get<{ sources: SourceInfo[] }>('/library/sources/')
  return data
}

/** Trigger ingestion for a specific source. */
export async function triggerIngestion(source: string): Promise<{ status: string; source: string }> {
  const { data } = await client.post<{ status: string; source: string }>(`/library/sources/${source}/ingest`)
  return data
}

/** Resume an interrupted ingestion from checkpoint. */
export async function resumeIngestion(source: string): Promise<{ status: string; source: string }> {
  const { data } = await client.post<{ status: string; source: string }>(`/library/sources/${source}/resume`)
  return data
}

/** Cancel a running ingestion. */
export async function cancelIngestion(source: string): Promise<{ status: string; source: string }> {
  const { data } = await client.post<{ status: string; source: string }>(`/library/sources/${source}/cancel`)
  return data
}

/** Trigger all (or selected) sources in parallel. */
export async function triggerAllSources(sources?: string[]): Promise<{ sources_started: string[] }> {
  const { data } = await client.post<{ sources_started: string[] }>('/library/sources/trigger-all', sources ?? null)
  return data
}

/** Resume all sources with pending checkpoints. */
export async function resumeAllSources(): Promise<{ sources_resumed: string[] }> {
  const { data } = await client.post<{ sources_resumed: string[] }>('/library/sources/resume-all')
  return data
}

/** Cancel all running ingestion sources. */
export async function cancelAllSources(): Promise<{ cancelled: boolean }> {
  const { data } = await client.post<{ cancelled: boolean }>('/library/sources/cancel-all')
  return data
}

/** Get per-source ingestion status. */
export async function getSourceStatus(): Promise<Record<string, unknown>> {
  const { data } = await client.get<Record<string, unknown>>('/library/sources/status')
  return data
}

/** List ingestion runs, optionally filtered by source. */
export async function listIngestionRuns(
  source?: string,
): Promise<{ runs: IngestionRunResponse[]; total: number }> {
  const { data } = await client.get<{ runs: IngestionRunResponse[]; total: number }>(
    '/library/ingestion-runs/',
    { params: source ? { source } : undefined },
  )
  return data
}

/** Get library statistics. */
export async function getStats(): Promise<LibraryStatsResponse> {
  const { data } = await client.get<LibraryStatsResponse>('/library/stats')
  return data
}
