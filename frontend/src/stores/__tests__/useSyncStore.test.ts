import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSyncStore } from '@/stores/useSyncStore'

vi.mock('@/api/sync', () => ({
  getSyncStatus: vi.fn(),
  getSyncHistory: vi.fn(),
  triggerSync: vi.fn(),
}))

import * as syncApi from '@/api/sync'
import type { SyncRun, SyncProgressMessage } from '@/types/sync'

const mockRun: SyncRun = {
  id: 'run-1',
  status: 'running',
  mode: 'full',
  trigger: 'manual',
  phase: 'agents',
  message: 'Syncing agents',
  counts: { sites_synced: 2, sites_total: 2, groups_synced: 5, groups_total: 5, agents_synced: 10, agents_total: 50, apps_synced: 0, apps_total: 0, tags_synced: 0, tags_total: 0, errors: 0 },
  started_at: '2025-01-01T00:00:00Z',
  completed_at: null,
}

describe('useSyncStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  describe('initial state', () => {
    it('starts with null/empty/default values', () => {
      const store = useSyncStore()
      expect(store.currentRun).toBeNull()
      expect(store.lastCompletedRun).toBeNull()
      expect(store.history).toEqual([])
      expect(store.historyTotal).toBe(0)
      expect(store.dbCounts).toBeNull()
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
    })
  })

  describe('fetchStatus', () => {
    it('populates currentRun and lastCompletedRun from API', async () => {
      const completedRun = { ...mockRun, id: 'run-0', status: 'completed' as const }
      vi.mocked(syncApi.getSyncStatus).mockResolvedValue({
        current_run: mockRun,
        last_completed_run: completedRun,
        db_counts: { sites: 1, groups: 2, agents: 10, apps: 100, tags: 50 },
      })

      const store = useSyncStore()
      await store.fetchStatus()

      expect(store.currentRun).toEqual(mockRun)
      expect(store.lastCompletedRun).toEqual(completedRun)
      expect(store.dbCounts).toEqual({ sites: 1, groups: 2, agents: 10, apps: 100, tags: 50 })
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('sets dbCounts to null when API omits it', async () => {
      vi.mocked(syncApi.getSyncStatus).mockResolvedValue({
        current_run: null,
        last_completed_run: null,
      } as any)

      const store = useSyncStore()
      await store.fetchStatus()

      expect(store.dbCounts).toBeNull()
    })

    it('sets error on API failure', async () => {
      vi.mocked(syncApi.getSyncStatus).mockRejectedValue(new Error('Network error'))

      const store = useSyncStore()
      await store.fetchStatus()

      expect(store.error).toBe('Network error')
      expect(store.isLoading).toBe(false)
    })

    it('sets generic error for non-Error throws', async () => {
      vi.mocked(syncApi.getSyncStatus).mockRejectedValue('string error')

      const store = useSyncStore()
      await store.fetchStatus()

      expect(store.error).toBe('Failed to fetch sync status')
    })
  })

  describe('fetchHistory', () => {
    it('populates history and historyTotal', async () => {
      const runs = [mockRun, { ...mockRun, id: 'run-2' }]
      vi.mocked(syncApi.getSyncHistory).mockResolvedValue({ runs, total: 42 })

      const store = useSyncStore()
      await store.fetchHistory(2, 10)

      expect(syncApi.getSyncHistory).toHaveBeenCalledWith(2, 10)
      expect(store.history).toEqual(runs)
      expect(store.historyTotal).toBe(42)
    })

    it('uses default page=1 and limit=20', async () => {
      vi.mocked(syncApi.getSyncHistory).mockResolvedValue({ runs: [], total: 0 })

      const store = useSyncStore()
      await store.fetchHistory()

      expect(syncApi.getSyncHistory).toHaveBeenCalledWith(1, 20)
    })

    it('sets error on failure', async () => {
      vi.mocked(syncApi.getSyncHistory).mockRejectedValue(new Error('timeout'))

      const store = useSyncStore()
      await store.fetchHistory()

      expect(store.error).toBe('timeout')
    })
  })

  describe('triggerSync', () => {
    it('triggers sync and returns true on success', async () => {
      vi.mocked(syncApi.triggerSync).mockResolvedValue(mockRun as any)

      const store = useSyncStore()
      const result = await store.triggerSync('full', ['sites', 'groups'])

      expect(syncApi.triggerSync).toHaveBeenCalledWith({ mode: 'full', phases: ['sites', 'groups'] })
      expect(result).toBe(true)
    })

    it('defaults to mode=auto with no phases', async () => {
      vi.mocked(syncApi.triggerSync).mockResolvedValue(mockRun as any)

      const store = useSyncStore()
      await store.triggerSync()

      expect(syncApi.triggerSync).toHaveBeenCalledWith({ mode: 'auto', phases: undefined })
    })

    it('returns false and sets error on failure', async () => {
      vi.mocked(syncApi.triggerSync).mockRejectedValue(new Error('409 Conflict'))

      const store = useSyncStore()
      const result = await store.triggerSync()

      expect(result).toBe(false)
      expect(store.error).toBe('409 Conflict')
    })
  })

  describe('handleProgressMessage', () => {
    it('ignores ping messages', () => {
      const store = useSyncStore()
      store.currentRun = { ...mockRun }

      store.handleProgressMessage({ type: 'ping' } as any)

      expect(store.currentRun.status).toBe('running')
    })

    it('updates currentRun in place when run_id matches', () => {
      const store = useSyncStore()
      store.currentRun = { ...mockRun }

      const msg: SyncProgressMessage = {
        type: 'progress',
        run_id: 'run-1',
        status: 'running',
        phase: 'apps',
        message: 'Syncing apps',
        counts: { sites_synced: 2, sites_total: 2, groups_synced: 5, groups_total: 5, agents_synced: 10, agents_total: 50, apps_synced: 50, apps_total: 100, tags_synced: 0, tags_total: 0, errors: 0 },
      }
      store.handleProgressMessage(msg)

      expect(store.currentRun!.phase).toBe('apps')
      expect(store.currentRun!.message).toBe('Syncing apps')
      expect(store.currentRun!.counts.apps_synced).toBe(50)
      // Previous counts preserved
      expect(store.currentRun!.counts.agents_synced).toBe(10)
    })

    it('adopts a new run when run_id changes', () => {
      const store = useSyncStore()
      store.currentRun = { ...mockRun }

      store.handleProgressMessage({
        type: 'progress',
        run_id: 'different-run',
        status: 'running',
        phase: 'apps',
        counts: {},
      } as any)

      // Store adopts the new run (e.g. after a restart/resume)
      expect(store.currentRun!.id).toBe('different-run')
      expect(store.currentRun!.phase).toBe('apps')
    })

    it('moves currentRun to lastCompletedRun on "completed"', () => {
      const store = useSyncStore()
      store.currentRun = { ...mockRun }

      store.handleProgressMessage({
        type: 'completed',
        run_id: 'run-1',
        status: 'completed',
        counts: {},
      } as any)

      expect(store.currentRun).toBeNull()
      expect(store.lastCompletedRun).toBeTruthy()
      expect(store.lastCompletedRun!.id).toBe('run-1')
    })

    it('prepends to history and increments total on completion', () => {
      const store = useSyncStore()
      store.currentRun = { ...mockRun }
      store.history = [{ ...mockRun, id: 'old-run' } as SyncRun]
      store.historyTotal = 1

      store.handleProgressMessage({
        type: 'completed',
        run_id: 'run-1',
        status: 'completed',
        counts: {},
      } as any)

      expect(store.history).toHaveLength(2)
      expect(store.history[0]!.id).toBe('run-1')
      expect(store.historyTotal).toBe(2)
    })

    it('handles "failed" type same as "completed"', () => {
      const store = useSyncStore()
      store.currentRun = { ...mockRun }

      store.handleProgressMessage({
        type: 'failed',
        run_id: 'run-1',
        status: 'failed',
        counts: {},
      } as any)

      expect(store.currentRun).toBeNull()
      expect(store.lastCompletedRun).toBeTruthy()
    })

    it('preserves existing phase/message when msg fields are nullish', () => {
      const store = useSyncStore()
      store.currentRun = { ...mockRun }

      store.handleProgressMessage({
        type: 'progress',
        run_id: 'run-1',
        status: 'running',
        phase: undefined,
        message: undefined,
        counts: {},
      } as any)

      expect(store.currentRun!.phase).toBe('agents')
      expect(store.currentRun!.message).toBe('Syncing agents')
    })
  })
})
