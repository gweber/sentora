import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import client from '@/api/client'
import {
  listWebhooks,
  getWebhook,
  createWebhook,
  updateWebhook,
  deleteWebhook,
  testWebhook,
} from '@/api/webhooks'
import type { Webhook, WebhookCreateRequest, WebhookUpdateRequest } from '@/types/webhooks'

const mockWebhook: Webhook = {
  id: 'wh1',
  name: 'Slack Alert',
  url: 'https://hooks.slack.com/test',
  events: ['sync.completed', 'sync.failed'],
  enabled: true,
  created_at: '2026-03-01T00:00:00Z',
  last_triggered_at: null,
  failure_count: 0,
}

describe('webhooks API', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('listWebhooks calls GET /webhooks/ and returns data', async () => {
    vi.mocked(client.get).mockResolvedValue({ data: [mockWebhook] })

    const result = await listWebhooks()

    expect(client.get).toHaveBeenCalledWith('/webhooks/')
    expect(result).toEqual([mockWebhook])
  })

  it('getWebhook calls GET /webhooks/{id}', async () => {
    vi.mocked(client.get).mockResolvedValue({ data: mockWebhook })

    const result = await getWebhook('wh1')

    expect(client.get).toHaveBeenCalledWith('/webhooks/wh1')
    expect(result).toEqual(mockWebhook)
  })

  it('createWebhook calls POST /webhooks/ with payload', async () => {
    const payload: WebhookCreateRequest = {
      name: 'Slack Alert',
      url: 'https://hooks.slack.com/test',
      events: ['sync.completed'],
    }
    vi.mocked(client.post).mockResolvedValue({ data: mockWebhook })

    const result = await createWebhook(payload)

    expect(client.post).toHaveBeenCalledWith('/webhooks/', payload)
    expect(result).toEqual(mockWebhook)
  })

  it('updateWebhook calls PUT /webhooks/{id} with payload', async () => {
    const payload: WebhookUpdateRequest = { name: 'Updated Name', enabled: false }
    const updated = { ...mockWebhook, name: 'Updated Name', enabled: false }
    vi.mocked(client.put).mockResolvedValue({ data: updated })

    const result = await updateWebhook('wh1', payload)

    expect(client.put).toHaveBeenCalledWith('/webhooks/wh1', payload)
    expect(result).toEqual(updated)
  })

  it('deleteWebhook calls DELETE /webhooks/{id}', async () => {
    vi.mocked(client.delete).mockResolvedValue({ data: undefined })

    await deleteWebhook('wh1')

    expect(client.delete).toHaveBeenCalledWith('/webhooks/wh1')
  })

  it('testWebhook calls POST /webhooks/{id}/test', async () => {
    const testResponse = { success: true, status_code: 200, response_time_ms: 150 }
    vi.mocked(client.post).mockResolvedValue({ data: testResponse })

    const result = await testWebhook('wh1')

    expect(client.post).toHaveBeenCalledWith('/webhooks/wh1/test')
    expect(result).toEqual(testResponse)
  })
})
