/**
 * Webhooks API — CRUD and test operations for webhook management.
 */

import client from './client'
import type {
  Webhook,
  WebhookCreateRequest,
  WebhookTestResponse,
  WebhookUpdateRequest,
} from '@/types/webhooks'

/** List all webhooks. */
export async function listWebhooks(): Promise<Webhook[]> {
  const { data } = await client.get<Webhook[]>('/webhooks/')
  return data
}

/** Get a single webhook by ID. */
export async function getWebhook(id: string): Promise<Webhook> {
  const { data } = await client.get<Webhook>(`/webhooks/${id}`)
  return data
}

/** Create a new webhook. */
export async function createWebhook(payload: WebhookCreateRequest): Promise<Webhook> {
  const { data } = await client.post<Webhook>('/webhooks/', payload)
  return data
}

/** Update a webhook. */
export async function updateWebhook(id: string, payload: WebhookUpdateRequest): Promise<Webhook> {
  const { data } = await client.put<Webhook>(`/webhooks/${id}`, payload)
  return data
}

/** Delete a webhook. */
export async function deleteWebhook(id: string): Promise<void> {
  await client.delete(`/webhooks/${id}`)
}

/** Send a test event to a webhook. */
export async function testWebhook(id: string): Promise<WebhookTestResponse> {
  const { data } = await client.post<WebhookTestResponse>(`/webhooks/${id}/test`)
  return data
}
