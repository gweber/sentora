/**
 * Sync store.
 *
 * Manages sync status, live progress (via WebSocket), and run history.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as syncApi from '@/api/sync'
import type { SyncRun, SyncMode, SyncStatusResponse, SyncProgressMessage, SyncDbCounts, PhaseProgress, PhaseSchedule } from '@/types/sync'

export const useSyncStore = defineStore('sync', () => {
  const currentRun = ref<SyncRun | null>(null)
  const lastCompletedRun = ref<SyncRun | null>(null)
  const history = ref<SyncRun[]>([])
  const historyTotal = ref(0)
  const dbCounts = ref<SyncDbCounts | null>(null)
  const phaseDetails = ref<Record<string, PhaseProgress>>({})
  const schedule = ref<Record<string, PhaseSchedule>>({})
  const error = ref<string | null>(null)

  // Separate loading flags to prevent race between concurrent fetches
  const _statusLoading = ref(false)
  const _historyLoading = ref(false)
  const isLoading = computed(() => _statusLoading.value || _historyLoading.value)

  async function fetchStatus(): Promise<void> {
    _statusLoading.value = true
    error.value = null
    try {
      const status: SyncStatusResponse = await syncApi.getSyncStatus()
      currentRun.value = status.current_run
      lastCompletedRun.value = status.last_completed_run
      dbCounts.value = status.db_counts ?? null
      schedule.value = status.schedule ?? {}
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch sync status'
    } finally {
      _statusLoading.value = false
    }
  }

  async function fetchHistory(page = 1, limit = 20): Promise<void> {
    _historyLoading.value = true
    try {
      const response = await syncApi.getSyncHistory(page, limit)
      history.value = response.runs
      historyTotal.value = response.total
    } catch (err) {
      if (!error.value) {
        error.value = err instanceof Error ? err.message : 'Failed to fetch sync history'
      }
    } finally {
      _historyLoading.value = false
    }
  }

  async function triggerSync(mode: SyncMode = 'auto', phases?: string[]): Promise<boolean> {
    error.value = null
    try {
      await syncApi.triggerSync({ mode, phases })
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to trigger sync'
      return false
    }
  }

  /** Handle a WebSocket progress message — updates the live run in-place. */
  function handleProgressMessage(msg: SyncProgressMessage): void {
    if (msg.type === 'ping') return

    // Always update phase_details when present
    if (msg.phase_details) {
      phaseDetails.value = msg.phase_details
    }

    // Adopt the run if we don't have one yet or if the run_id changed (e.g. resume after restart)
    if (!currentRun.value || currentRun.value.id !== msg.run_id) {
      currentRun.value = {
        id: msg.run_id,
        status: msg.status,
        phase: msg.phase ?? null,
        message: msg.message ?? null,
        counts: msg.counts ?? {},
      } as SyncRun
    } else {
      currentRun.value = {
        ...currentRun.value,
        status: msg.status,
        phase: msg.phase ?? currentRun.value.phase,
        message: msg.message ?? currentRun.value.message,
        counts: { ...currentRun.value.counts, ...msg.counts },
      }
    }

    if (msg.type === 'completed' || msg.type === 'failed') {
      lastCompletedRun.value = currentRun.value
      // Prepend to history
      if (currentRun.value) {
        history.value = [currentRun.value, ...history.value]
        historyTotal.value++
      }
      currentRun.value = null
      phaseDetails.value = {}
      // Refresh server state (dbCounts, schedule, history) now that the sync is done.
      fetchStatus().catch(() => {})
      fetchHistory().catch(() => {})
    }
  }

  return {
    currentRun,
    lastCompletedRun,
    dbCounts,
    phaseDetails,
    schedule,
    history,
    historyTotal,
    isLoading,
    error,
    fetchStatus,
    fetchHistory,
    triggerSync,
    handleProgressMessage,
  }
})
