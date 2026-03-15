import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useClassificationStore } from '@/stores/useClassificationStore'

vi.mock('@/api/classification', () => ({
  getOverview: vi.fn(),
  listResults: vi.fn(),
  triggerClassification: vi.fn(),
  acknowledgeAnomaly: vi.fn(),
  exportResults: vi.fn(),
}))

import * as classApi from '@/api/classification'
import type { ClassificationOverview, ClassificationResult } from '@/types/classification'

const mockOverview: ClassificationOverview = {
  total: 100,
  correct: 80,
  misclassified: 10,
  ambiguous: 5,
  unclassifiable: 5,
  groups_count: 3,
  anomalies: 2,
  last_computed_at: '2025-01-01T00:00:00Z',
}

const mockResult: ClassificationResult = {
  agent_id: 'a1',
  agent_name: 'Agent 1',
  group_id: 'g1',
  group_name: 'Group 1',
  classification: 'correct',
  score: 0.95,
  acknowledged: false,
}

describe('useClassificationStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('initial state', () => {
    it('starts with null/empty/false defaults', () => {
      const store = useClassificationStore()
      expect(store.overview).toBeNull()
      expect(store.results).toEqual([])
      expect(store.resultsTotal).toBe(0)
      expect(store.isLoading).toBe(false)
      expect(store.isRunning).toBe(false)
      expect(store.error).toBeNull()
    })
  })

  describe('fetchOverview', () => {
    it('populates overview from API', async () => {
      vi.mocked(classApi.getOverview).mockResolvedValue(mockOverview)

      const store = useClassificationStore()
      await store.fetchOverview()

      expect(store.overview).toEqual(mockOverview)
      expect(store.isLoading).toBe(false)
    })

    it('sets error on failure', async () => {
      vi.mocked(classApi.getOverview).mockRejectedValue(new Error('Down'))

      const store = useClassificationStore()
      await store.fetchOverview()

      expect(store.error).toBe('Down')
    })
  })

  describe('fetchResults', () => {
    it('populates results with filters', async () => {
      vi.mocked(classApi.listResults).mockResolvedValue({
        results: [mockResult],
        total: 1,
      })

      const store = useClassificationStore()
      await store.fetchResults({ page: 1, limit: 20, classification: 'correct', search: 'Agent' })

      expect(classApi.listResults).toHaveBeenCalledWith({
        page: 1,
        limit: 20,
        classification: 'correct',
        search: 'Agent',
      })
      expect(store.results).toEqual([mockResult])
      expect(store.resultsTotal).toBe(1)
    })

    it('handles empty results', async () => {
      vi.mocked(classApi.listResults).mockResolvedValue({ results: [], total: 0 })

      const store = useClassificationStore()
      await store.fetchResults({})

      expect(store.results).toEqual([])
      expect(store.resultsTotal).toBe(0)
    })

    it('sets error on failure', async () => {
      vi.mocked(classApi.listResults).mockRejectedValue(new Error('Timeout'))

      const store = useClassificationStore()
      await store.fetchResults({})

      expect(store.error).toBe('Timeout')
    })
  })

  describe('triggerClassification', () => {
    it('triggers and sets isRunning, starts polling', async () => {
      vi.mocked(classApi.triggerClassification).mockResolvedValue(undefined)

      const store = useClassificationStore()
      await store.triggerClassification()

      expect(store.isRunning).toBe(true)
      expect(store.error).toBeNull()
    })

    it('does nothing if already running', async () => {
      const store = useClassificationStore()
      store.isRunning = true

      await store.triggerClassification()

      expect(classApi.triggerClassification).not.toHaveBeenCalled()
    })

    it('handles 409 by setting isRunning=true and error message', async () => {
      vi.mocked(classApi.triggerClassification).mockRejectedValue(
        new Error('409 already in progress'),
      )

      const store = useClassificationStore()
      await store.triggerClassification()

      expect(store.isRunning).toBe(true)
      expect(store.error).toBe('A classification run is already in progress.')
    })

    it('sets generic error for non-409 failures', async () => {
      vi.mocked(classApi.triggerClassification).mockRejectedValue(
        new Error('500 Internal Server Error'),
      )

      const store = useClassificationStore()
      await store.triggerClassification()

      expect(store.isRunning).toBe(false)
      expect(store.error).toBe('500 Internal Server Error')
    })

    it('polling stops when last_computed_at changes', async () => {
      vi.mocked(classApi.triggerClassification).mockResolvedValue(undefined)
      const freshOverview = { ...mockOverview, last_computed_at: '2025-01-02T00:00:00Z' }
      vi.mocked(classApi.getOverview).mockResolvedValue(freshOverview)

      const store = useClassificationStore()
      store.overview = { ...mockOverview }

      await store.triggerClassification()
      expect(store.isRunning).toBe(true)

      // Advance past the 3-second poll interval
      await vi.advanceTimersByTimeAsync(3000)

      expect(classApi.getOverview).toHaveBeenCalled()
      expect(store.isRunning).toBe(false)
      expect(store.overview!.last_computed_at).toBe('2025-01-02T00:00:00Z')
    })

    it('keeps polling when last_computed_at has not changed', async () => {
      vi.mocked(classApi.triggerClassification).mockResolvedValue(undefined)
      // Return same last_computed_at
      vi.mocked(classApi.getOverview).mockResolvedValue({ ...mockOverview })

      const store = useClassificationStore()
      store.overview = { ...mockOverview }

      await store.triggerClassification()

      // First poll
      await vi.advanceTimersByTimeAsync(3000)
      expect(store.isRunning).toBe(true)

      // Second poll
      await vi.advanceTimersByTimeAsync(3000)
      expect(store.isRunning).toBe(true)
      expect(classApi.getOverview).toHaveBeenCalledTimes(2)
    })
  })

  describe('acknowledgeAnomaly', () => {
    it('marks agent result as acknowledged', async () => {
      vi.mocked(classApi.acknowledgeAnomaly).mockResolvedValue(undefined)

      const store = useClassificationStore()
      store.results = [{ ...mockResult }, { ...mockResult, agent_id: 'a2' }]

      await store.acknowledgeAnomaly('a1')

      expect(store.results[0].acknowledged).toBe(true)
      expect(store.results[1].acknowledged).toBe(false)
    })

    it('sets error on failure', async () => {
      vi.mocked(classApi.acknowledgeAnomaly).mockRejectedValue(new Error('Not found'))

      const store = useClassificationStore()
      await store.acknowledgeAnomaly('a1')

      expect(store.error).toBe('Not found')
    })
  })

  describe('exportResults', () => {
    it('creates download link for CSV blob', async () => {
      const blob = new Blob(['csv data'], { type: 'text/csv' })
      vi.mocked(classApi.exportResults).mockResolvedValue(blob)

      const mockClick = vi.fn()
      vi.spyOn(document, 'createElement').mockReturnValue({
        href: '',
        download: '',
        click: mockClick,
      } as any)

      const store = useClassificationStore()
      await store.exportResults('csv', { classification: 'correct' })

      expect(classApi.exportResults).toHaveBeenCalledWith('csv', { classification: 'correct' })
      expect(mockClick).toHaveBeenCalled()
    })

    it('sets error on export failure', async () => {
      vi.mocked(classApi.exportResults).mockRejectedValue(new Error('Export failed'))

      const store = useClassificationStore()
      await store.exportResults('json')

      expect(store.error).toBe('Export failed')
    })
  })
})
