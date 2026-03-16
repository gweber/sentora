/**
 * Fingerprint store.
 *
 * Manages fingerprints, markers, and suggestions. The fingerprint editor
 * drives most of this store's state.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as fingerprintApi from '@/api/fingerprints'
import type {
  Fingerprint,
  FingerprintMarker,
  FingerprintSuggestion,
  MarkerCreateRequest,
  MarkerUpdateRequest,
} from '@/types/fingerprint'

export const useFingerprintStore = defineStore('fingerprint', () => {
  const activeFingerprint = ref<Fingerprint | null>(null)
  const suggestions = ref<FingerprintSuggestion[]>([])
  const isLoading = ref(false)
  const isSuggestionsLoading = ref(false)
  const error = ref<string | null>(null)

  /** Load a specific group's fingerprint and set it as active. */
  async function loadFingerprint(groupId: string): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      activeFingerprint.value = await fingerprintApi.getFingerprint(groupId)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      if (msg.includes('FINGERPRINT_NOT_FOUND') || msg.includes('404')) {
        // 404 means no fingerprint yet — that's fine
        activeFingerprint.value = null
        error.value = null
      } else {
        activeFingerprint.value = null
        error.value = msg || 'Failed to load fingerprint'
      }
    } finally {
      isLoading.value = false
    }
  }

  /** Create a fingerprint for a group if one doesn't exist yet. */
  async function ensureFingerprint(groupId: string): Promise<void> {
    if (activeFingerprint.value?.group_id === groupId) return
    isLoading.value = true
    try {
      try {
        activeFingerprint.value = await fingerprintApi.getFingerprint(groupId)
      } catch {
        activeFingerprint.value = await fingerprintApi.createFingerprint(groupId)
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load fingerprint'
    } finally {
      isLoading.value = false
    }
  }

  /** Add a marker to the active fingerprint. */
  async function addMarker(payload: MarkerCreateRequest): Promise<FingerprintMarker | null> {
    if (!activeFingerprint.value) return null
    isLoading.value = true
    error.value = null
    try {
      const marker = await fingerprintApi.addMarker(activeFingerprint.value.group_id, payload)
      activeFingerprint.value.markers.push(marker)
      return marker
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to add marker'
      return null
    } finally {
      isLoading.value = false
    }
  }

  /** Update a marker (weight, pattern, etc.). */
  async function updateMarker(
    markerId: string,
    payload: MarkerUpdateRequest,
  ): Promise<void> {
    if (!activeFingerprint.value) return
    try {
      const updated = await fingerprintApi.updateMarker(
        activeFingerprint.value.group_id,
        markerId,
        payload,
      )
      const idx = activeFingerprint.value.markers.findIndex((m) => m.id === markerId)
      if (idx >= 0) activeFingerprint.value.markers[idx] = updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update marker'
    }
  }

  /** Remove a marker from the active fingerprint. */
  async function removeMarker(markerId: string): Promise<void> {
    if (!activeFingerprint.value) return
    try {
      await fingerprintApi.deleteMarker(activeFingerprint.value.group_id, markerId)
      activeFingerprint.value.markers = activeFingerprint.value.markers.filter(
        (m) => m.id !== markerId,
      )
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to remove marker'
    }
  }

  /** Reorder markers after a drag-and-drop operation. */
  async function reorderMarkers(orderedIds: string[]): Promise<void> {
    if (!activeFingerprint.value) return
    // Optimistically reorder locally first
    const markerMap = new Map(activeFingerprint.value.markers.map((m) => [m.id, m]))
    activeFingerprint.value.markers = orderedIds
      .map((id) => markerMap.get(id))
      .filter((m): m is FingerprintMarker => Boolean(m))

    try {
      await fingerprintApi.reorderMarkers(activeFingerprint.value.group_id, orderedIds)
    } catch (err) {
      // Show error before reloading to restore correct order
      error.value = 'Failed to reorder markers. Reloading...'
      await loadFingerprint(activeFingerprint.value.group_id)
    }
  }

  /** Load statistical suggestions for the active group. */
  async function loadSuggestions(groupId: string): Promise<void> {
    isSuggestionsLoading.value = true
    try {
      suggestions.value = await fingerprintApi.getSuggestions(groupId)
    } catch {
      suggestions.value = []
    } finally {
      isSuggestionsLoading.value = false
    }
  }

  /** Accept a suggestion (adds it as a marker). */
  async function acceptSuggestion(suggestionId: string): Promise<void> {
    if (!activeFingerprint.value) return
    try {
      await fingerprintApi.acceptSuggestion(activeFingerprint.value.group_id, suggestionId)
      suggestions.value = suggestions.value.filter((s) => s.id !== suggestionId)
      // Reload fingerprint to pick up the new marker
      await loadFingerprint(activeFingerprint.value.group_id)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to accept suggestion'
    }
  }

  /** Reject a suggestion. */
  async function rejectSuggestion(suggestionId: string): Promise<void> {
    if (!activeFingerprint.value) return
    try {
      await fingerprintApi.rejectSuggestion(activeFingerprint.value.group_id, suggestionId)
      suggestions.value = suggestions.value.filter((s) => s.id !== suggestionId)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to reject suggestion'
    }
  }

  return {
    activeFingerprint,
    suggestions,
    isLoading,
    isSuggestionsLoading,
    error,
    loadFingerprint,
    ensureFingerprint,
    addMarker,
    updateMarker,
    removeMarker,
    reorderMarkers,
    loadSuggestions,
    acceptSuggestion,
    rejectSuggestion,
  }
})
