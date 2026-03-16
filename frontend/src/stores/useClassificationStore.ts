/**
 * Classification store.
 *
 * Manages classification overview, paginated results, and anomaly list.
 */

import { defineStore } from 'pinia'
import { onScopeDispose, ref } from 'vue'
import * as classificationApi from '@/api/classification'
import type {
  ClassificationOverview,
  ClassificationResult,
  ClassificationVerdict,
} from '@/types/classification'

export const useClassificationStore = defineStore('classification', () => {
  const overview = ref<ClassificationOverview | null>(null)
  const results = ref<ClassificationResult[]>([])
  const resultsTotal = ref(0)
  const isLoading = ref(false)
  const isRunning = ref(false)
  const error = ref<string | null>(null)

  let _pollTimer: ReturnType<typeof setTimeout> | null = null

  /** Fetch the classification overview summary. */
  async function fetchOverview(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      overview.value = await classificationApi.getOverview()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch overview'
    } finally {
      isLoading.value = false
    }
  }

  /** Fetch paginated classification results with optional filters. */
  async function fetchResults(params: {
    page?: number
    limit?: number
    classification?: ClassificationVerdict | ''
    group_id?: string
    search?: string
  }): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      const response = await classificationApi.listResults(params)
      results.value = response.results
      resultsTotal.value = response.total
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch results'
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Trigger a full reclassification run, then poll overview until
   * last_computed_at advances (indicating run completion).
   */
  async function triggerClassification(): Promise<void> {
    if (isRunning.value) return
    error.value = null
    try {
      await classificationApi.triggerClassification()
      isRunning.value = true
      _startPolling()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg.includes('409') || msg.includes('already in progress')) {
        error.value = 'A classification run is already in progress.'
        isRunning.value = true
        _startPolling()
      } else {
        error.value = msg
      }
    }
  }

  function _startPolling(): void {
    if (_pollTimer) return
    const baseline = overview.value?.last_computed_at ?? null
    const MAX_POLL_ITERATIONS = 120 // ~6 minutes at 3s intervals
    let pollCount = 0

    async function poll() {
      pollCount++
      if (pollCount > MAX_POLL_ITERATIONS) {
        isRunning.value = false
        _pollTimer = null
        error.value = 'Classification is taking longer than expected. Please refresh to check status.'
        return
      }
      try {
        const fresh = await classificationApi.getOverview()
        if (fresh.last_computed_at !== baseline) {
          overview.value = fresh
          isRunning.value = false
          _pollTimer = null
          return
        }
        overview.value = fresh
      } catch {
        // keep polling
      }
      _pollTimer = setTimeout(poll, 3000)
    }

    _pollTimer = setTimeout(poll, 3000)
  }

  /**
   * Stop the classification polling timer.
   *
   * Should be called when leaving the classification view to prevent
   * the recursive setTimeout chain from running indefinitely.
   */
  function stopPolling(): void {
    if (_pollTimer) {
      clearTimeout(_pollTimer)
      _pollTimer = null
    }
  }

  // Automatically stop polling when the store's scope is disposed
  // (e.g. when the owning component unmounts).
  onScopeDispose(stopPolling)

  /** Mark an anomaly as acknowledged. */
  async function acknowledgeAnomaly(agentId: string): Promise<void> {
    try {
      await classificationApi.acknowledgeAnomaly(agentId)
      const result = results.value.find((r) => r.agent_id === agentId)
      if (result) result.acknowledged = true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to acknowledge anomaly'
    }
  }

  /** Download export file and trigger browser save dialog, respecting active filters. */
  async function exportResults(
    format: 'csv' | 'json',
    filters?: { classification?: string; search?: string; group_id?: string },
  ): Promise<void> {
    try {
      const blob = await classificationApi.exportResults(format, filters)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `classification_results.${format}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Export failed'
    }
  }

  return {
    overview,
    results,
    resultsTotal,
    isLoading,
    isRunning,
    error,
    fetchOverview,
    fetchResults,
    triggerClassification,
    acknowledgeAnomaly,
    exportResults,
    stopPolling,
  }
})
