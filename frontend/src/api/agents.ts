/**
 * Agent domain API calls.
 */

import type { AgentDetailResponse, AgentListResponse, InstalledApplication } from '@/types/agent'
import client from './client'

/** List agents with optional filters and pagination. */
export async function listAgents(params: {
  page?: number
  limit?: number
  group_id?: string
  classification?: string
  search?: string
}): Promise<AgentListResponse> {
  const { data } = await client.get<AgentListResponse>('/agents/', { params })
  return data
}

/** Get full agent detail including installed apps and classification. */
export async function getAgent(agentId: string): Promise<AgentDetailResponse> {
  const { data } = await client.get<AgentDetailResponse>(`/agents/${agentId}`)
  return data
}

/** Get the installed applications list for an agent. */
export async function getAgentApps(agentId: string): Promise<InstalledApplication[]> {
  const { data } = await client.get<InstalledApplication[]>(`/agents/${agentId}/apps`)
  return data
}
