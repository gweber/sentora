/**
 * API Keys store — manages API key CRUD state for the management UI.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as apiKeysApi from '@/api/apiKeys'
import type { APIKeyResponse, APIKeyCreateRequest, APIKeyUpdateRequest } from '@/types/apiKeys'

export const useApiKeysStore = defineStore('apiKeys', () => {
  const keys = ref<APIKeyResponse[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const activeKeys = computed(() => keys.value.filter(k => k.is_active))
  const revokedKeys = computed(() => keys.value.filter(k => !k.is_active))

  async function load(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      keys.value = await apiKeysApi.listApiKeys()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load API keys'
    } finally {
      isLoading.value = false
    }
  }

  async function create(req: APIKeyCreateRequest): Promise<string | null> {
    error.value = null
    try {
      const resp = await apiKeysApi.createApiKey(req)
      keys.value.unshift(resp.key)
      return resp.full_key
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to create API key'
      return null
    }
  }

  async function update(id: string, req: APIKeyUpdateRequest): Promise<boolean> {
    error.value = null
    try {
      const updated = await apiKeysApi.updateApiKey(id, req)
      const idx = keys.value.findIndex(k => k.id === id)
      if (idx >= 0) keys.value[idx] = updated
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update API key'
      return false
    }
  }

  async function revoke(id: string): Promise<boolean> {
    error.value = null
    try {
      await apiKeysApi.revokeApiKey(id)
      const idx = keys.value.findIndex(k => k.id === id)
      if (idx >= 0) {
        keys.value[idx] = { ...keys.value[idx], is_active: false, revoked_at: new Date().toISOString() }
      }
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to revoke API key'
      return false
    }
  }

  async function rotate(id: string): Promise<string | null> {
    error.value = null
    try {
      const resp = await apiKeysApi.rotateApiKey(id)
      // Mark old key as revoked, add new key
      const idx = keys.value.findIndex(k => k.id === id)
      if (idx >= 0) {
        keys.value[idx] = { ...keys.value[idx], is_active: false, revoked_at: new Date().toISOString() }
      }
      keys.value.unshift(resp.key)
      return resp.full_key
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to rotate API key'
      return null
    }
  }

  return {
    keys,
    isLoading,
    error,
    activeKeys,
    revokedKeys,
    load,
    create,
    update,
    revoke,
    rotate,
  }
})
