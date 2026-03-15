import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useFingerprintStore } from '@/stores/useFingerprintStore'

vi.mock('@/api/fingerprints', () => ({
  getFingerprint: vi.fn(),
  createFingerprint: vi.fn(),
  addMarker: vi.fn(),
  updateMarker: vi.fn(),
  deleteMarker: vi.fn(),
  reorderMarkers: vi.fn(),
  getSuggestions: vi.fn(),
  acceptSuggestion: vi.fn(),
  rejectSuggestion: vi.fn(),
}))

import * as fpApi from '@/api/fingerprints'
import type { Fingerprint, FingerprintMarker } from '@/types/fingerprint'

const marker1: FingerprintMarker = {
  id: 'm1',
  pattern: 'chrome*',
  weight: 1.0,
  field: 'name',
  match_type: 'glob',
}

const marker2: FingerprintMarker = {
  id: 'm2',
  pattern: 'firefox*',
  weight: 0.5,
  field: 'name',
  match_type: 'glob',
}

const mockFingerprint: Fingerprint = {
  group_id: 'g1',
  markers: [marker1, marker2],
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

describe('useFingerprintStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  describe('initial state', () => {
    it('starts with null/empty defaults', () => {
      const store = useFingerprintStore()
      expect(store.activeFingerprint).toBeNull()
      expect(store.suggestions).toEqual([])
      expect(store.isLoading).toBe(false)
      expect(store.isSuggestionsLoading).toBe(false)
      expect(store.error).toBeNull()
    })
  })

  describe('loadFingerprint', () => {
    it('sets activeFingerprint from API', async () => {
      vi.mocked(fpApi.getFingerprint).mockResolvedValue(mockFingerprint)

      const store = useFingerprintStore()
      await store.loadFingerprint('g1')

      expect(fpApi.getFingerprint).toHaveBeenCalledWith('g1')
      expect(store.activeFingerprint).toEqual(mockFingerprint)
      expect(store.isLoading).toBe(false)
    })

    it('sets activeFingerprint to null on 404 without setting error', async () => {
      const axiosError: any = new Error('404 Not Found')
      axiosError.response = { status: 404 }
      vi.mocked(fpApi.getFingerprint).mockRejectedValue(axiosError)

      const store = useFingerprintStore()
      await store.loadFingerprint('nonexistent')

      expect(store.activeFingerprint).toBeNull()
      expect(store.error).toBeNull()
      expect(store.isLoading).toBe(false)
    })
  })

  describe('ensureFingerprint', () => {
    it('skips API call if active fingerprint already matches group', async () => {
      const store = useFingerprintStore()
      store.activeFingerprint = { ...mockFingerprint }

      await store.ensureFingerprint('g1')

      expect(fpApi.getFingerprint).not.toHaveBeenCalled()
    })

    it('fetches existing fingerprint if available', async () => {
      vi.mocked(fpApi.getFingerprint).mockResolvedValue(mockFingerprint)

      const store = useFingerprintStore()
      await store.ensureFingerprint('g1')

      expect(store.activeFingerprint).toEqual(mockFingerprint)
      expect(fpApi.createFingerprint).not.toHaveBeenCalled()
    })

    it('creates fingerprint when get fails', async () => {
      vi.mocked(fpApi.getFingerprint).mockRejectedValue(new Error('404'))
      vi.mocked(fpApi.createFingerprint).mockResolvedValue(mockFingerprint)

      const store = useFingerprintStore()
      await store.ensureFingerprint('g1')

      expect(fpApi.createFingerprint).toHaveBeenCalledWith('g1')
      expect(store.activeFingerprint).toEqual(mockFingerprint)
    })

    it('sets error when both get and create fail', async () => {
      vi.mocked(fpApi.getFingerprint).mockRejectedValue(new Error('404'))
      vi.mocked(fpApi.createFingerprint).mockRejectedValue(new Error('Server error'))

      const store = useFingerprintStore()
      await store.ensureFingerprint('g1')

      expect(store.error).toBe('Server error')
    })
  })

  describe('addMarker', () => {
    it('adds marker to activeFingerprint markers array', async () => {
      const newMarker: FingerprintMarker = { id: 'm3', pattern: 'slack*', weight: 0.8, field: 'name', match_type: 'glob' }
      vi.mocked(fpApi.addMarker).mockResolvedValue(newMarker)

      const store = useFingerprintStore()
      store.activeFingerprint = { ...mockFingerprint, markers: [...mockFingerprint.markers] }

      const result = await store.addMarker({ pattern: 'slack*', weight: 0.8, field: 'name', match_type: 'glob' })

      expect(result).toEqual(newMarker)
      expect(store.activeFingerprint!.markers).toHaveLength(3)
      expect(store.activeFingerprint!.markers[2]).toEqual(newMarker)
    })

    it('returns null when no activeFingerprint', async () => {
      const store = useFingerprintStore()
      const result = await store.addMarker({ pattern: 'x', weight: 1, field: 'name', match_type: 'glob' })
      expect(result).toBeNull()
      expect(fpApi.addMarker).not.toHaveBeenCalled()
    })

    it('sets error on API failure', async () => {
      vi.mocked(fpApi.addMarker).mockRejectedValue(new Error('Conflict'))

      const store = useFingerprintStore()
      store.activeFingerprint = { ...mockFingerprint, markers: [] }

      const result = await store.addMarker({ pattern: 'x', weight: 1, field: 'name', match_type: 'glob' })
      expect(result).toBeNull()
      expect(store.error).toBe('Conflict')
    })
  })

  describe('updateMarker', () => {
    it('replaces marker in array by id', async () => {
      const updated = { ...marker1, weight: 0.3 }
      vi.mocked(fpApi.updateMarker).mockResolvedValue(updated)

      const store = useFingerprintStore()
      store.activeFingerprint = { ...mockFingerprint, markers: [{ ...marker1 }, { ...marker2 }] }

      await store.updateMarker('m1', { weight: 0.3 })

      expect(store.activeFingerprint!.markers[0].weight).toBe(0.3)
    })

    it('does nothing when no activeFingerprint', async () => {
      const store = useFingerprintStore()
      await store.updateMarker('m1', { weight: 0.3 })
      expect(fpApi.updateMarker).not.toHaveBeenCalled()
    })

    it('sets error on failure', async () => {
      vi.mocked(fpApi.updateMarker).mockRejectedValue(new Error('Bad request'))

      const store = useFingerprintStore()
      store.activeFingerprint = { ...mockFingerprint, markers: [{ ...marker1 }] }

      await store.updateMarker('m1', { weight: -1 })
      expect(store.error).toBe('Bad request')
    })
  })

  describe('removeMarker', () => {
    it('removes marker from array', async () => {
      vi.mocked(fpApi.deleteMarker).mockResolvedValue(undefined)

      const store = useFingerprintStore()
      store.activeFingerprint = { ...mockFingerprint, markers: [{ ...marker1 }, { ...marker2 }] }

      await store.removeMarker('m1')

      expect(store.activeFingerprint!.markers).toHaveLength(1)
      expect(store.activeFingerprint!.markers[0].id).toBe('m2')
    })

    it('does nothing when no activeFingerprint', async () => {
      const store = useFingerprintStore()
      await store.removeMarker('m1')
      expect(fpApi.deleteMarker).not.toHaveBeenCalled()
    })
  })

  describe('reorderMarkers', () => {
    it('optimistically reorders markers locally', async () => {
      vi.mocked(fpApi.reorderMarkers).mockResolvedValue(undefined)

      const store = useFingerprintStore()
      store.activeFingerprint = { ...mockFingerprint, markers: [{ ...marker1 }, { ...marker2 }] }

      await store.reorderMarkers(['m2', 'm1'])

      expect(store.activeFingerprint!.markers[0].id).toBe('m2')
      expect(store.activeFingerprint!.markers[1].id).toBe('m1')
    })

    it('reloads fingerprint on API failure (rollback)', async () => {
      vi.mocked(fpApi.reorderMarkers).mockRejectedValue(new Error('fail'))
      vi.mocked(fpApi.getFingerprint).mockResolvedValue(mockFingerprint)

      const store = useFingerprintStore()
      store.activeFingerprint = { ...mockFingerprint, markers: [{ ...marker1 }, { ...marker2 }] }

      await store.reorderMarkers(['m2', 'm1'])

      // Should have called loadFingerprint which calls getFingerprint
      expect(fpApi.getFingerprint).toHaveBeenCalledWith('g1')
    })

    it('filters out unknown marker ids gracefully', async () => {
      vi.mocked(fpApi.reorderMarkers).mockResolvedValue(undefined)

      const store = useFingerprintStore()
      store.activeFingerprint = { ...mockFingerprint, markers: [{ ...marker1 }, { ...marker2 }] }

      await store.reorderMarkers(['m2', 'nonexistent', 'm1'])

      // nonexistent is filtered out
      expect(store.activeFingerprint!.markers).toHaveLength(2)
    })
  })

  describe('loadSuggestions', () => {
    it('populates suggestions from API', async () => {
      const mockSuggestions = [{ id: 's1', normalized_name: 'chrome', score: 0.9 }]
      vi.mocked(fpApi.getSuggestions).mockResolvedValue(mockSuggestions as any)

      const store = useFingerprintStore()
      await store.loadSuggestions('g1')

      expect(store.suggestions).toEqual(mockSuggestions)
      expect(store.isSuggestionsLoading).toBe(false)
    })

    it('sets empty array on failure', async () => {
      vi.mocked(fpApi.getSuggestions).mockRejectedValue(new Error('fail'))

      const store = useFingerprintStore()
      store.suggestions = [{ id: 'old' } as any]

      await store.loadSuggestions('g1')

      expect(store.suggestions).toEqual([])
    })
  })

  describe('acceptSuggestion', () => {
    it('removes accepted suggestion and reloads fingerprint', async () => {
      vi.mocked(fpApi.acceptSuggestion).mockResolvedValue(undefined)
      vi.mocked(fpApi.getFingerprint).mockResolvedValue(mockFingerprint)

      const store = useFingerprintStore()
      store.activeFingerprint = { ...mockFingerprint, markers: [] }
      store.suggestions = [{ id: 's1' } as any, { id: 's2' } as any]

      await store.acceptSuggestion('s1')

      expect(store.suggestions).toHaveLength(1)
      expect(store.suggestions[0].id).toBe('s2')
      expect(fpApi.getFingerprint).toHaveBeenCalled()
    })

    it('does nothing when no activeFingerprint', async () => {
      const store = useFingerprintStore()
      await store.acceptSuggestion('s1')
      expect(fpApi.acceptSuggestion).not.toHaveBeenCalled()
    })
  })

  describe('rejectSuggestion', () => {
    it('removes rejected suggestion from list', async () => {
      vi.mocked(fpApi.rejectSuggestion).mockResolvedValue(undefined)

      const store = useFingerprintStore()
      store.activeFingerprint = { ...mockFingerprint }
      store.suggestions = [{ id: 's1' } as any, { id: 's2' } as any]

      await store.rejectSuggestion('s1')

      expect(store.suggestions).toHaveLength(1)
      expect(store.suggestions[0].id).toBe('s2')
    })

    it('sets error on failure', async () => {
      vi.mocked(fpApi.rejectSuggestion).mockRejectedValue(new Error('Server error'))

      const store = useFingerprintStore()
      store.activeFingerprint = { ...mockFingerprint }

      await store.rejectSuggestion('s1')

      expect(store.error).toBe('Server error')
    })
  })
})
