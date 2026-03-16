/**
 * API Keys API — CRUD, rotation, and self-info for tenant-scoped API keys.
 */

import client from './client'
import type {
  APIKeyCreateRequest,
  APIKeyCreateResponse,
  APIKeyCurrentResponse,
  APIKeyResponse,
  APIKeyRotateResponse,
  APIKeyUpdateRequest,
} from '@/types/apiKeys'

export async function listApiKeys(): Promise<APIKeyResponse[]> {
  const resp = await client.get<APIKeyResponse[]>('/api-keys/')
  return resp.data
}

export async function getApiKey(id: string): Promise<APIKeyResponse> {
  const resp = await client.get<APIKeyResponse>(`/api-keys/${id}`)
  return resp.data
}

export async function createApiKey(data: APIKeyCreateRequest): Promise<APIKeyCreateResponse> {
  const resp = await client.post<APIKeyCreateResponse>('/api-keys/', data)
  return resp.data
}

export async function updateApiKey(id: string, data: APIKeyUpdateRequest): Promise<APIKeyResponse> {
  const resp = await client.put<APIKeyResponse>(`/api-keys/${id}`, data)
  return resp.data
}

export async function revokeApiKey(id: string): Promise<void> {
  await client.delete(`/api-keys/${id}`)
}

export async function rotateApiKey(id: string): Promise<APIKeyRotateResponse> {
  const resp = await client.post<APIKeyRotateResponse>(`/api-keys/${id}/rotate`)
  return resp.data
}

export async function getCurrentApiKey(): Promise<APIKeyCurrentResponse> {
  const resp = await client.get<APIKeyCurrentResponse>('/api-keys/current')
  return resp.data
}
