/**
 * API client for audit hash-chain operations.
 *
 * Provides typed functions for chain verification, status, epoch listing,
 * and epoch export.  All endpoints require at minimum analyst-level access.
 */

import client from './client'

// ── Types ──────────────────────────────────────────────────────────────────

export interface VerifyChainRequest {
  epoch: number | null
}

export interface VerifyChainResponse {
  status: 'valid' | 'broken' | 'gap_detected'
  verified_entries: number
  first_sequence: number
  last_sequence: number
  epochs_verified: number
  broken_at_sequence: number | null
  broken_reason: string | null
  verification_time_ms: number
}

export interface ChainStatusResponse {
  total_entries: number
  current_epoch: number
  current_sequence: number
  genesis_hash: string
  latest_hash: string
  chain_valid: boolean | null
  last_verified_at: string | null
}

export interface EpochSummary {
  epoch: number
  first_sequence: number
  last_sequence: number
  entry_count: number
  first_timestamp: string
  last_timestamp: string
  epoch_final_hash: string
  previous_epoch_hash: string | null
  exported: boolean
}

export interface EpochListResponse {
  epochs: EpochSummary[]
  total: number
}

// ── API Functions ──────────────────────────────────────────────────────────

export async function getChainStatus(): Promise<ChainStatusResponse> {
  const { data } = await client.get<ChainStatusResponse>('/audit/chain/status')
  return data
}

export async function verifyChain(
  request: VerifyChainRequest = { epoch: null },
): Promise<VerifyChainResponse> {
  const { data } = await client.post<VerifyChainResponse>('/audit/chain/verify', request)
  return data
}

export async function listEpochs(): Promise<EpochListResponse> {
  const { data } = await client.get<EpochListResponse>('/audit/chain/epochs')
  return data
}

export async function exportEpoch(epochNumber: number): Promise<Blob> {
  const { data } = await client.post(`/audit/chain/export/${epochNumber}`, null, {
    responseType: 'blob',
  })
  return data as Blob
}

export async function initializeChain(): Promise<void> {
  await client.post('/audit/chain/initialize')
}
