/**
 * Apps domain API calls.
 */

import type { AppDetail, AppListResponse } from '@/types/app'
import client from './client'

/** List all distinct applications in the fleet (paginated). */
export async function listApps(params?: {
  q?: string
  sort?: string
  order?: string
  page?: number
  limit?: number
}): Promise<AppListResponse> {
  const { data } = await client.get<AppListResponse>('/apps/', { params })
  return data
}

/** Fetch fleet-wide detail for a normalised application name. */
export async function getAppDetail(normalizedName: string): Promise<AppDetail> {
  const { data } = await client.get<AppDetail>(`/apps/${encodeURIComponent(normalizedName)}`)
  return data
}
