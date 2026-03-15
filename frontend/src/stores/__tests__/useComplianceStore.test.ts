/**
 * Tests for the compliance Pinia store.
 *
 * All API calls are mocked at the HTTP boundary (vi.mock on the API module).
 * Tests verify state mutations, error handling, and getter derivations.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useComplianceStore } from '@/stores/useComplianceStore'

vi.mock('@/api/compliance', () => ({
  listFrameworks: vi.fn(),
  getFrameworkDetail: vi.fn(),
  enableFramework: vi.fn(),
  disableFramework: vi.fn(),
  getDashboard: vi.fn(),
  getLatestResults: vi.fn(),
  listViolations: vi.fn(),
  runCompliance: vi.fn(),
  configureControl: vi.fn(),
  createCustomControl: vi.fn(),
  getControlHistory: vi.fn(),
  getSchedule: vi.fn(),
  updateSchedule: vi.fn(),
}))

import * as complianceApi from '@/api/compliance'
import type {
  FrameworkSummary,
  DashboardResponse,
  LatestResultsResponse,
  RunResultResponse,
  ScheduleResponse,
} from '@/api/compliance'

const mockFramework: FrameworkSummary = {
  id: 'soc2',
  name: 'SOC 2 Type II',
  version: '2024',
  description: 'Trust Services Criteria',
  disclaimer: 'Not certification',
  enabled: true,
  total_controls: 15,
  enabled_controls: 15,
}

const mockDashboard: DashboardResponse = {
  frameworks: [
    {
      framework_id: 'soc2',
      framework_name: 'SOC 2 Type II',
      total_controls: 15,
      passed: 12,
      failed: 2,
      warning: 1,
      error: 0,
      not_applicable: 0,
      score_percent: 80.0,
    },
  ],
  overall_score_percent: 80.0,
  total_violations: 5,
  last_run_at: '2025-01-01T00:00:00Z',
}

const mockResults: LatestResultsResponse = {
  results: [
    {
      control_id: 'SOC2-CC6.7',
      framework_id: 'soc2',
      control_name: 'No Prohibited Software',
      category: 'CC6',
      severity: 'critical',
      status: 'pass',
      checked_at: '2025-01-01T00:00:00Z',
      total_endpoints: 100,
      compliant_endpoints: 100,
      non_compliant_endpoints: 0,
      evidence_summary: 'All clear',
      violations: [],
    },
  ],
  total: 1,
  checked_at: '2025-01-01T00:00:00Z',
}

const mockRunResult: RunResultResponse = {
  run_id: 'run-1',
  status: 'completed',
  controls_evaluated: 15,
  passed: 12,
  failed: 2,
  warning: 1,
  duration_ms: 500,
}

const mockSchedule: ScheduleResponse = {
  run_after_sync: true,
  cron_expression: null,
  enabled: true,
  updated_at: null,
  updated_by: null,
}

describe('useComplianceStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  describe('initial state', () => {
    it('starts with empty/null default values', () => {
      const store = useComplianceStore()
      expect(store.frameworks).toEqual([])
      expect(store.dashboard).toBeNull()
      expect(store.latestResults).toBeNull()
      expect(store.violations).toBeNull()
      expect(store.schedule).toBeNull()
      expect(store.isLoading).toBe(false)
      expect(store.isRunning).toBe(false)
      expect(store.error).toBeNull()
    })
  })

  describe('fetchFrameworks', () => {
    it('populates frameworks from API', async () => {
      vi.mocked(complianceApi.listFrameworks).mockResolvedValue({
        frameworks: [mockFramework],
      })

      const store = useComplianceStore()
      await store.fetchFrameworks()

      expect(store.frameworks).toEqual([mockFramework])
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('sets error on API failure', async () => {
      vi.mocked(complianceApi.listFrameworks).mockRejectedValue(
        new Error('Network error'),
      )

      const store = useComplianceStore()
      await store.fetchFrameworks()

      expect(store.error).toBe('Network error')
      expect(store.isLoading).toBe(false)
    })
  })

  describe('toggleFramework', () => {
    it('enables a framework and updates local state', async () => {
      vi.mocked(complianceApi.enableFramework).mockResolvedValue(undefined)

      const store = useComplianceStore()
      store.frameworks = [{ ...mockFramework, enabled: false }]

      await store.toggleFramework('soc2', true)

      expect(complianceApi.enableFramework).toHaveBeenCalledWith('soc2')
      expect(store.frameworks[0].enabled).toBe(true)
    })

    it('disables a framework and updates local state', async () => {
      vi.mocked(complianceApi.disableFramework).mockResolvedValue(undefined)

      const store = useComplianceStore()
      store.frameworks = [{ ...mockFramework, enabled: true }]

      await store.toggleFramework('soc2', false)

      expect(complianceApi.disableFramework).toHaveBeenCalledWith('soc2')
      expect(store.frameworks[0].enabled).toBe(false)
    })
  })

  describe('fetchDashboard', () => {
    it('populates dashboard and computes getters', async () => {
      vi.mocked(complianceApi.getDashboard).mockResolvedValue(mockDashboard)

      const store = useComplianceStore()
      await store.fetchDashboard()

      expect(store.dashboard).toEqual(mockDashboard)
      expect(store.overallScore).toBe(80.0)
      expect(store.totalViolations).toBe(5)
    })
  })

  describe('fetchLatestResults', () => {
    it('populates latest results', async () => {
      vi.mocked(complianceApi.getLatestResults).mockResolvedValue(mockResults)

      const store = useComplianceStore()
      await store.fetchLatestResults()

      expect(store.latestResults).toEqual(mockResults)
      expect(store.latestResults!.total).toBe(1)
    })

    it('passes framework filter to API', async () => {
      vi.mocked(complianceApi.getLatestResults).mockResolvedValue(mockResults)

      const store = useComplianceStore()
      await store.fetchLatestResults('soc2')

      expect(complianceApi.getLatestResults).toHaveBeenCalledWith('soc2')
    })
  })

  describe('triggerRun', () => {
    it('sets isRunning during execution and populates lastRunResult', async () => {
      vi.mocked(complianceApi.runCompliance).mockResolvedValue(mockRunResult)

      const store = useComplianceStore()
      await store.triggerRun()

      expect(store.lastRunResult).toEqual(mockRunResult)
      expect(store.isRunning).toBe(false)
    })

    it('sets error on failure', async () => {
      vi.mocked(complianceApi.runCompliance).mockRejectedValue(
        new Error('Run failed'),
      )

      const store = useComplianceStore()
      await store.triggerRun()

      expect(store.error).toBe('Run failed')
      expect(store.isRunning).toBe(false)
    })
  })

  describe('fetchSchedule', () => {
    it('populates schedule from API', async () => {
      vi.mocked(complianceApi.getSchedule).mockResolvedValue(mockSchedule)

      const store = useComplianceStore()
      await store.fetchSchedule()

      expect(store.schedule).toEqual(mockSchedule)
    })
  })

  describe('updateSchedule', () => {
    it('sends update and refreshes local schedule', async () => {
      const updated = { ...mockSchedule, run_after_sync: false }
      vi.mocked(complianceApi.updateSchedule).mockResolvedValue(updated)

      const store = useComplianceStore()
      await store.updateSchedule({ run_after_sync: false })

      expect(store.schedule).toEqual(updated)
      expect(complianceApi.updateSchedule).toHaveBeenCalledWith({
        run_after_sync: false,
      })
    })
  })

  describe('enabledFrameworks getter', () => {
    it('filters to only enabled frameworks', () => {
      const store = useComplianceStore()
      store.frameworks = [
        { ...mockFramework, id: 'soc2', enabled: true },
        { ...mockFramework, id: 'hipaa', enabled: false },
        { ...mockFramework, id: 'bsi_grundschutz', enabled: true },
      ]

      expect(store.enabledFrameworks).toHaveLength(2)
      expect(store.enabledFrameworks.map(f => f.id)).toEqual([
        'soc2',
        'bsi_grundschutz',
      ])
    })
  })
})
