/** Fingerprint Library domain types — mirrors backend DTOs. */

export interface LibraryMarker {
  id: string
  pattern: string
  display_name: string
  category: string
  weight: number
  source_detail: string
  added_at: string
  added_by: string
}

export interface LibraryEntry {
  id: string
  name: string
  vendor: string
  category: string
  description: string
  tags: string[]
  markers: LibraryMarker[]
  source: string
  upstream_id: string | null
  upstream_version: string | null
  version: number
  status: string
  subscriber_count: number
  submitted_by: string
  reviewed_by: string | null
  created_at: string
  updated_at: string
}

export interface LibraryEntryListResponse {
  entries: LibraryEntry[]
  total: number
}

export interface LibraryEntryCreateRequest {
  name: string
  vendor?: string
  category?: string
  description?: string
  tags?: string[]
  markers?: { pattern: string; display_name?: string; weight?: number }[]
}

export interface LibraryEntryUpdateRequest {
  name?: string
  vendor?: string
  category?: string
  description?: string
  tags?: string[]
  status?: string
}

export interface SubscriptionResponse {
  id: string
  group_id: string
  library_entry_id: string
  entry_name: string
  synced_version: number
  auto_update: boolean
  subscribed_at: string
  subscribed_by: string
  last_synced_at: string | null
}

export interface SubscriptionListResponse {
  subscriptions: SubscriptionResponse[]
  total: number
}

export interface IngestionRunResponse {
  id: string
  source: string
  status: string
  started_at: string
  completed_at: string | null
  entries_created: number
  entries_updated: number
  entries_skipped: number
  errors: string[]
}

export interface SourceInfo {
  name: string
  description: string
  status: string
  last_run: IngestionRunResponse | null
}

export interface LibraryStatsResponse {
  total_entries: number
  by_source: Record<string, number>
  by_status: Record<string, number>
  total_subscriptions: number
}

/** Per-source status snapshot included in WebSocket broadcasts. */
export interface SourceProgress {
  status: string
  synced: number
  total: number
  message?: string
}

/** Real-time ingestion progress received over WebSocket. */
export interface IngestionProgressMessage {
  type: 'progress' | 'completed' | 'failed' | 'source_completed' | 'source_failed' | 'source_cancelled'
  run_id: string
  source: string
  status: string
  message?: string
  entries_created: number
  entries_updated: number
  entries_skipped: number
  total_processed: number
  error_count: number
  source_details?: Record<string, SourceProgress>
}
