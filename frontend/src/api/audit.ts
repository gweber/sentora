import client from './client'

export interface AuditEntry {
  timestamp: string
  actor: string
  domain: string
  action: string
  status: string
  summary: string
  details: Record<string, unknown>
}

export interface AuditListResponse {
  entries: AuditEntry[]
  total: number
  page: number
  limit: number
}

export interface AuditQuery {
  page?: number
  limit?: number
  domain?: string
  actor?: string
  action?: string
  status?: string
}

export async function getAuditLog(query: AuditQuery = {}): Promise<AuditListResponse> {
  const params: Record<string, string> = {}
  if (query.page !== undefined)  params.page   = String(query.page)
  if (query.limit !== undefined) params.limit  = String(query.limit)
  if (query.domain) params.domain = query.domain
  if (query.actor)  params.actor  = query.actor
  if (query.action) params.action = query.action
  if (query.status) params.status = query.status
  const { data } = await client.get<AuditListResponse>('/audit/', { params })
  return data
}
