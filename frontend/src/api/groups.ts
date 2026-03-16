/**
 * Groups API module.
 *
 * Wraps HTTP calls to the groups and sites endpoints, replacing
 * direct `client.get()` calls in GroupsView.
 */

import client from './client'

export interface Site {
  s1_site_id: string
  name: string
  state: string
  site_type: string
  account_id: string
  account_name: string
  group_count: number
  agent_count: number
}

export interface Group {
  group_id: string
  group_name: string | null
  description: string | null
  type: string
  is_default: boolean
  filter_name: string | null
  site_id: string
  site_name: string
  agent_count: number
  os_types: string[]
  created_at: string | null
  updated_at: string | null
  has_fingerprint: boolean
}

export interface SitesResponse {
  sites: Site[]
}

export interface GroupsResponse {
  groups: Group[]
}

/**
 * List all sites for the current tenant.
 *
 * @param limit - Maximum number of sites to return.
 */
export async function listSites(limit = 500): Promise<SitesResponse> {
  const { data } = await client.get<SitesResponse>('/sites/', { params: { limit } })
  return data
}

/**
 * List all groups for the current tenant.
 *
 * @param limit - Maximum number of groups to return.
 */
export async function listGroups(limit = 1000): Promise<GroupsResponse> {
  const { data } = await client.get<GroupsResponse>('/groups/', { params: { limit } })
  return data
}
