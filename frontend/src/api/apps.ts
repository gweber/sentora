/**
 * Apps domain API calls.
 */

import type { AppAgentsResponse, AppDetail, AppListResponse, AppStats } from '@/types/app'
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

/** Fetch stats, breakdowns, taxonomy, and EOL for an application (no agent list). */
export async function getAppStats(normalizedName: string): Promise<AppStats> {
  const { data } = await client.get<AppStats>(
    `/apps/stats/${encodeURIComponent(normalizedName)}`,
  )
  return data
}

/** Fetch paginated, filterable agent list for an application. */
export async function getAppAgents(
  normalizedName: string,
  opts: {
    page?: number
    pageSize?: number
    groupNames?: string[]
    siteNames?: string[]
    versions?: string[]
    search?: string
  } = {},
): Promise<AppAgentsResponse> {
  const params = new URLSearchParams()
  if (opts.page) params.set('page', String(opts.page))
  if (opts.pageSize) params.set('page_size', String(opts.pageSize))
  for (const g of opts.groupNames ?? []) params.append('group_name', g)
  for (const s of opts.siteNames ?? []) params.append('site_name', s)
  for (const v of opts.versions ?? []) params.append('version', v)
  if (opts.search) params.set('search', opts.search)

  const { data } = await client.get<AppAgentsResponse>(
    `/apps/agents/${encodeURIComponent(normalizedName)}?${params.toString()}`,
  )
  return data
}

/**
 * Fetch fleet-wide detail for a normalised application name.
 * @deprecated Use getAppStats() + getAppAgents() for better performance.
 */
export async function getAppDetail(
  normalizedName: string,
  opts: {
    page?: number
    pageSize?: number
    groupNames?: string[]
    siteNames?: string[]
    versions?: string[]
    search?: string
  } = {},
): Promise<AppDetail> {
  const params = new URLSearchParams()
  if (opts.page) params.set('page', String(opts.page))
  if (opts.pageSize) params.set('page_size', String(opts.pageSize))
  for (const g of opts.groupNames ?? []) params.append('group_name', g)
  for (const s of opts.siteNames ?? []) params.append('site_name', s)
  for (const v of opts.versions ?? []) params.append('version', v)
  if (opts.search) params.set('search', opts.search)

  const { data } = await client.get<AppDetail>(
    `/apps/${encodeURIComponent(normalizedName)}?${params.toString()}`,
  )
  return data
}
