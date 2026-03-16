import client from './client'

export interface Tenant {
  id: string
  name: string
  slug: string
  database_name: string
  created_at: string
  disabled: boolean
  plan: string
}

export interface TenantListResponse {
  tenants: Tenant[]
  total: number
}

export interface TenantCreatePayload {
  name: string
  slug: string
  database_name?: string
  plan?: string
}

export interface TenantUpdatePayload {
  name?: string
  disabled?: boolean
  plan?: string
}

export async function listTenants(): Promise<TenantListResponse> {
  const { data } = await client.get<TenantListResponse>('/tenants/')
  return data
}

export async function getTenant(slug: string): Promise<Tenant> {
  const { data } = await client.get<Tenant>(`/tenants/${slug}`)
  return data
}

export async function createTenant(payload: TenantCreatePayload): Promise<Tenant> {
  const { data } = await client.post<Tenant>('/tenants/', payload)
  return data
}

export async function updateTenant(slug: string, payload: TenantUpdatePayload): Promise<Tenant> {
  const { data } = await client.patch<Tenant>(`/tenants/${slug}`, payload)
  return data
}

export async function deleteTenant(slug: string): Promise<void> {
  await client.delete(`/tenants/${slug}`)
}
