/**
 * Classification domain API calls.
 */

import type {
  ClassificationOverview,
  ClassificationResult,
  ClassificationResultListResponse,
} from '@/types/classification'
import client from './client'

/** Get the classification overview summary. */
export async function getOverview(): Promise<ClassificationOverview> {
  const { data } = await client.get<ClassificationOverview>('/classification/overview')
  return data
}

/** Get paginated classification results with optional filters. */
export async function listResults(params: {
  page?: number
  limit?: number
  classification?: string
  group_id?: string
  search?: string
}): Promise<ClassificationResultListResponse> {
  const { data } = await client.get<ClassificationResultListResponse>('/classification/results', {
    params,
  })
  return data
}

/** Get the classification result for a single agent. */
export async function getResult(agentId: string): Promise<ClassificationResult> {
  const { data } = await client.get<ClassificationResult>(`/classification/results/${agentId}`)
  return data
}

/** Trigger a full reclassification. */
export async function triggerClassification(): Promise<void> {
  await client.post('/classification/trigger')
}

/** Mark an agent's anomaly as acknowledged. */
export async function acknowledgeAnomaly(agentId: string): Promise<void> {
  await client.post(`/classification/acknowledge/${agentId}`)
}

/** Export classification results as CSV or JSON, with optional filters. */
export async function exportResults(
  format: 'csv' | 'json',
  filters?: { classification?: string; search?: string; group_id?: string },
): Promise<Blob> {
  const { data } = await client.get('/classification/export', {
    params: { format, ...filters },
    responseType: 'blob',
  })
  return data
}
