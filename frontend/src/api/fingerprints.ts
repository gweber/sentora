/**
 * Fingerprint domain API calls.
 */

import type {
  ApplyProposalResult,
  AutoFingerprintProposal,
  Fingerprint,
  FingerprintMarker,
  FingerprintSuggestion,
  MarkerCreateRequest,
  MarkerUpdateRequest,
} from '@/types/fingerprint'
import client from './client'

/** List all fingerprints (summary), with pagination. */
export async function listFingerprints(limit = 1000): Promise<Fingerprint[]> {
  const { data } = await client.get<{ fingerprints: Fingerprint[] }>('/fingerprints/', {
    params: { limit },
  })
  return data.fingerprints
}

/** Get the full fingerprint for a group. */
export async function getFingerprint(groupId: string): Promise<Fingerprint> {
  const { data } = await client.get<Fingerprint>(`/fingerprints/${groupId}`)
  return data
}

/** Create a new fingerprint for a group. */
export async function createFingerprint(groupId: string): Promise<Fingerprint> {
  const { data } = await client.post<Fingerprint>(`/fingerprints/${groupId}`)
  return data
}

/** Add a marker to a fingerprint. */
export async function addMarker(
  groupId: string,
  payload: MarkerCreateRequest,
): Promise<FingerprintMarker> {
  const { data } = await client.post<FingerprintMarker>(
    `/fingerprints/${groupId}/markers`,
    payload,
  )
  return data
}

/** Update a marker (weight, pattern, etc.). */
export async function updateMarker(
  groupId: string,
  markerId: string,
  payload: MarkerUpdateRequest,
): Promise<FingerprintMarker> {
  const { data } = await client.patch<FingerprintMarker>(
    `/fingerprints/${groupId}/markers/${markerId}`,
    payload,
  )
  return data
}

/** Delete a marker from a fingerprint. */
export async function deleteMarker(groupId: string, markerId: string): Promise<void> {
  await client.delete(`/fingerprints/${groupId}/markers/${markerId}`)
}

/** Reorder markers in a fingerprint. */
export async function reorderMarkers(groupId: string, markerIds: string[]): Promise<void> {
  await client.put(`/fingerprints/${groupId}/markers/order`, { marker_ids: markerIds })
}

/** Get statistical suggestions for a group. */
export async function getSuggestions(groupId: string, limit = 200): Promise<FingerprintSuggestion[]> {
  const { data } = await client.get<FingerprintSuggestion[]>(`/suggestions/${groupId}`, {
    params: { limit },
  })
  return data
}

/** Trigger suggestion computation for a group and return fresh results. */
export async function computeSuggestions(groupId: string): Promise<FingerprintSuggestion[]> {
  const { data } = await client.post<FingerprintSuggestion[]>(`/suggestions/${groupId}/compute`)
  return data
}

/** Accept a suggestion (adds it as a marker). */
export async function acceptSuggestion(groupId: string, suggestionId: string): Promise<void> {
  await client.post(`/suggestions/${groupId}/accept/${suggestionId}`)
}

/** Reject a suggestion. */
export async function rejectSuggestion(groupId: string, suggestionId: string): Promise<void> {
  await client.post(`/suggestions/${groupId}/reject/${suggestionId}`)
}

// ── Auto-fingerprint proposals ────────────────────────────────────────────────

/** Trigger background generation of Lift-based proposals for all groups. */
export async function generateProposals(): Promise<{ status: string }> {
  const { data } = await client.post<{ status: string }>('/fingerprints/proposals/generate')
  return data
}

/** List all proposals (excluding dismissed by default). */
export async function listProposals(showDismissed = false): Promise<AutoFingerprintProposal[]> {
  const { data } = await client.get<AutoFingerprintProposal[]>('/fingerprints/proposals/', {
    params: { show_dismissed: showDismissed },
  })
  return data
}

/** Apply a proposal's markers to the group fingerprint (add-only). */
export async function applyProposal(groupId: string): Promise<ApplyProposalResult> {
  const { data } = await client.post<ApplyProposalResult>(
    `/fingerprints/proposals/${groupId}/apply`,
  )
  return data
}

/** Dismiss a proposal (hides it from the default list). */
export async function dismissProposal(groupId: string): Promise<void> {
  await client.post(`/fingerprints/proposals/${groupId}/dismiss`)
}

// ── Import / Export ──────────────────────────────────────────────────────────

/** Export all fingerprints as a JSON file download. */
export async function exportFingerprints(): Promise<void> {
  const resp = await client.get('/fingerprints/export', { responseType: 'blob' })
  const blob = new Blob([resp.data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'fingerprints_export.json'
  a.click()
  URL.revokeObjectURL(url)
}

/** Import fingerprints from a JSON payload. */
export async function importFingerprints(
  items: import('@/types/fingerprint').FingerprintExportItem[],
  strategy: 'merge' | 'replace' = 'merge',
): Promise<import('@/types/fingerprint').FingerprintImportResponse> {
  const { data } = await client.post<import('@/types/fingerprint').FingerprintImportResponse>(
    '/fingerprints/import',
    { items },
    { params: { strategy } },
  )
  return data
}
