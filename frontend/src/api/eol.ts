/**
 * EOL domain API calls.
 *
 * Provides functions for interacting with the endoflife.date
 * lifecycle data source and EOL match review endpoints.
 */

import client from './client'

/** EOL source status info for the Library Sources UI. */
export interface EOLSourceInfo {
  name: string
  display_name: string
  last_synced: string | null
  total_products: number
  total_eol_cycles: number
  matched_apps: number
  status: string
}

/** EOL sync status. */
export interface EOLSyncStatus {
  last_synced: string | null
  total_products: number
  status: string
  message: string
}

/** EOL product in list view. */
export interface EOLProduct {
  product_id: string
  name: string
  last_synced: string | null
  total_cycles: number
  eol_cycles: number
  matched_apps: number
}

/** Paginated EOL product list. */
export interface EOLProductListResponse {
  products: EOLProduct[]
  total: number
  page: number
  page_size: number
}

/** Fuzzy match pending review. */
export interface EOLFuzzyMatchReviewItem {
  app_name: string
  normalized_name: string
  suggested_product_id: string
  suggested_product_name: string
  confidence: number
  agent_count: number
}

/** Fuzzy match review list. */
export interface EOLFuzzyMatchReviewResponse {
  items: EOLFuzzyMatchReviewItem[]
  total: number
}

/** Real-time progress message from the EOL sync WebSocket. */
export interface EOLSyncProgressMessage {
  type: 'progress' | 'completed' | 'failed' | 'snapshot'
  source: string
  status: string
  message: string
  products_synced: number
  products_failed: number
  products_total: number
  apps_matched?: number
  phase?: string
}

/** Fetch EOL source info for the library sources card. */
export async function getSourceInfo(): Promise<EOLSourceInfo> {
  const { data } = await client.get<EOLSourceInfo>('/eol/source')
  return data
}

/** Trigger an EOL data sync. */
export async function triggerSync(): Promise<EOLSyncStatus> {
  const { data } = await client.post<EOLSyncStatus>('/eol/sync')
  return data
}

/** Get current sync status. */
export async function getSyncStatus(): Promise<EOLSyncStatus> {
  const { data } = await client.get<EOLSyncStatus>('/eol/sync/status')
  return data
}

/** List EOL products with pagination and search. */
export async function listProducts(params?: {
  search?: string
  page?: number
  page_size?: number
}): Promise<EOLProductListResponse> {
  const { data } = await client.get<EOLProductListResponse>('/eol/products', { params })
  return data
}

/** Get fuzzy matches pending review. */
export async function listFuzzyMatches(params?: {
  page?: number
  page_size?: number
}): Promise<EOLFuzzyMatchReviewResponse> {
  const { data } = await client.get<EOLFuzzyMatchReviewResponse>('/eol/matches/review', { params })
  return data
}

/** Confirm or dismiss a fuzzy match. */
export async function reviewMatch(body: {
  normalized_name: string
  eol_product_id: string
  action: 'confirm' | 'dismiss'
}): Promise<{ status: string }> {
  const { data } = await client.post<{ status: string }>('/eol/matches/review', body)
  return data
}

// ── Name mappings ────────────────────────────────────────────────────────────

/** A single name → EOL product mapping. */
export interface NameMappingItem {
  app_name_prefix: string
  eol_product_id: string
  updated_at: string | null
  created_at: string | null
}

/** All name mappings (built-in + user). */
export interface NameMappingListResponse {
  builtin: NameMappingItem[]
  custom: NameMappingItem[]
  total_builtin: number
  total_custom: number
}

/** Fetch all name mappings. */
export async function listNameMappings(): Promise<NameMappingListResponse> {
  const { data } = await client.get<NameMappingListResponse>('/eol/mappings')
  return data
}

/** Create or update a custom name mapping. */
export async function upsertNameMapping(body: {
  app_name_prefix: string
  eol_product_id: string
}): Promise<{ status: string }> {
  const { data } = await client.put<{ status: string }>('/eol/mappings', body)
  return data
}

/** Delete a custom name mapping. */
export async function deleteNameMapping(appNamePrefix: string): Promise<{ status: string }> {
  const { data } = await client.delete<{ status: string }>(`/eol/mappings/${encodeURIComponent(appNamePrefix)}`)
  return data
}
