import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useApiKeysStore } from '@/stores/useApiKeysStore'

vi.mock('@/api/apiKeys', () => ({
  listApiKeys: vi.fn(),
  getApiKey: vi.fn(),
  createApiKey: vi.fn(),
  updateApiKey: vi.fn(),
  revokeApiKey: vi.fn(),
  rotateApiKey: vi.fn(),
  getCurrentApiKey: vi.fn(),
}))

import * as apiKeysApi from '@/api/apiKeys'
import type { APIKeyResponse, APIKeyCreateResponse, APIKeyRotateResponse } from '@/types/apiKeys'

const mockKey: APIKeyResponse = {
  id: 'k1',
  tenant_id: 'default',
  name: 'Splunk Integration',
  description: null,
  key_prefix: 'sentora_sk_live_a8f3',
  scopes: ['agents:read', 'apps:read'],
  rate_limit_per_minute: 60,
  rate_limit_per_hour: 1000,
  created_at: '2026-01-01T00:00:00Z',
  created_by: 'admin',
  expires_at: null,
  last_used_at: null,
  last_used_ip: null,
  is_active: true,
  revoked_at: null,
  revoked_by: null,
}

const mockCreateResponse: APIKeyCreateResponse = {
  key: mockKey,
  full_key: 'sentora_sk_live_a8f3b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3',
}

describe('useApiKeysStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  describe('initial state', () => {
    it('starts with empty defaults', () => {
      const store = useApiKeysStore()
      expect(store.keys).toEqual([])
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
      expect(store.activeKeys).toEqual([])
      expect(store.revokedKeys).toEqual([])
    })
  })

  describe('load', () => {
    it('populates keys from API', async () => {
      vi.mocked(apiKeysApi.listApiKeys).mockResolvedValue([mockKey])

      const store = useApiKeysStore()
      await store.load()

      expect(store.keys).toEqual([mockKey])
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('sets error on API failure', async () => {
      vi.mocked(apiKeysApi.listApiKeys).mockRejectedValue(new Error('Network error'))

      const store = useApiKeysStore()
      await store.load()

      expect(store.keys).toEqual([])
      expect(store.error).toBe('Network error')
    })

    it('sets isLoading during request', async () => {
      let resolvePromise: (value: APIKeyResponse[]) => void
      vi.mocked(apiKeysApi.listApiKeys).mockImplementation(
        () => new Promise((resolve) => { resolvePromise = resolve }),
      )

      const store = useApiKeysStore()
      const loadPromise = store.load()

      expect(store.isLoading).toBe(true)
      resolvePromise!([mockKey])
      await loadPromise
      expect(store.isLoading).toBe(false)
    })
  })

  describe('create', () => {
    it('returns full key and adds to store', async () => {
      vi.mocked(apiKeysApi.createApiKey).mockResolvedValue(mockCreateResponse)

      const store = useApiKeysStore()
      const fullKey = await store.create({
        name: 'Splunk Integration',
        scopes: ['agents:read', 'apps:read'],
      })

      expect(fullKey).toBe(mockCreateResponse.full_key)
      expect(store.keys).toHaveLength(1)
      expect(store.keys[0]!.name).toBe('Splunk Integration')
    })

    it('returns null on failure', async () => {
      vi.mocked(apiKeysApi.createApiKey).mockRejectedValue(new Error('Forbidden'))

      const store = useApiKeysStore()
      const fullKey = await store.create({ name: 'Test', scopes: ['agents:read'] })

      expect(fullKey).toBeNull()
      expect(store.error).toBe('Forbidden')
    })
  })

  describe('update', () => {
    it('updates key in store', async () => {
      const updatedKey = { ...mockKey, name: 'Updated Name' }
      vi.mocked(apiKeysApi.updateApiKey).mockResolvedValue(updatedKey)

      const store = useApiKeysStore()
      store.keys = [mockKey]

      const ok = await store.update('k1', { name: 'Updated Name' })

      expect(ok).toBe(true)
      expect(store.keys[0]!.name).toBe('Updated Name')
    })
  })

  describe('revoke', () => {
    it('marks key as inactive in store', async () => {
      vi.mocked(apiKeysApi.revokeApiKey).mockResolvedValue()

      const store = useApiKeysStore()
      store.keys = [mockKey]

      const ok = await store.revoke('k1')

      expect(ok).toBe(true)
      expect(store.keys[0]!.is_active).toBe(false)
    })
  })

  describe('rotate', () => {
    it('returns new full key and updates store', async () => {
      const rotateResponse: APIKeyRotateResponse = {
        key: { ...mockKey, id: 'k2', key_prefix: 'sentora_sk_live_new1' },
        full_key: 'sentora_sk_live_new1new2new3new4new5new6new7new8new9new0new1new2',
      }
      vi.mocked(apiKeysApi.rotateApiKey).mockResolvedValue(rotateResponse)

      const store = useApiKeysStore()
      store.keys = [mockKey]

      const fullKey = await store.rotate('k1')

      expect(fullKey).toBe(rotateResponse.full_key)
      expect(store.keys).toHaveLength(2) // old (revoked) + new
      expect(store.keys[0]!.is_active).toBe(true) // new key at front
      expect(store.keys[1]!.is_active).toBe(false) // old key revoked
    })
  })

  describe('computed', () => {
    it('activeKeys filters active keys', () => {
      const revokedKey = { ...mockKey, id: 'k2', is_active: false }

      const store = useApiKeysStore()
      store.keys = [mockKey, revokedKey]

      expect(store.activeKeys).toHaveLength(1)
      expect(store.activeKeys[0]!.id).toBe('k1')
    })

    it('revokedKeys filters revoked keys', () => {
      const revokedKey = { ...mockKey, id: 'k2', is_active: false }

      const store = useApiKeysStore()
      store.keys = [mockKey, revokedKey]

      expect(store.revokedKeys).toHaveLength(1)
      expect(store.revokedKeys[0]!.id).toBe('k2')
    })
  })
})
