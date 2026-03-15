/**
 * Pinia store for compliance domain state management.
 *
 * Manages framework listing, dashboard data, check results, violations,
 * and schedule configuration.  API calls are mocked at the HTTP boundary
 * in tests.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as complianceApi from '@/api/compliance'
import type {
  FrameworkSummary,
  FrameworkDetailResponse,
  DashboardResponse,
  LatestResultsResponse,
  ViolationListResponse,
  RunResultResponse,
  ScheduleResponse,
  ControlHistoryResponse,
  ConfigureControlRequest,
  CreateCustomControlRequest,
  UpdateScheduleRequest,
} from '@/api/compliance'

export const useComplianceStore = defineStore('compliance', () => {
  // ── State ──────────────────────────────────────────────────────────
  const frameworks = ref<FrameworkSummary[]>([])
  const activeFramework = ref<FrameworkDetailResponse | null>(null)
  const dashboard = ref<DashboardResponse | null>(null)
  const latestResults = ref<LatestResultsResponse | null>(null)
  const violations = ref<ViolationListResponse | null>(null)
  const schedule = ref<ScheduleResponse | null>(null)
  const controlHistory = ref<ControlHistoryResponse | null>(null)
  const lastRunResult = ref<RunResultResponse | null>(null)

  const isLoading = ref(false)
  const isRunning = ref(false)
  const error = ref<string | null>(null)

  // ── Getters ────────────────────────────────────────────────────────

  /** Enabled frameworks only. */
  const enabledFrameworks = computed(() =>
    frameworks.value.filter(f => f.enabled),
  )

  /** Overall compliance score from dashboard. */
  const overallScore = computed(() =>
    dashboard.value?.overall_score_percent ?? 0,
  )

  /** Total violation count from dashboard. */
  const totalViolations = computed(() =>
    dashboard.value?.total_violations ?? 0,
  )

  // ── Actions ────────────────────────────────────────────────────────

  /** Fetch all available frameworks. */
  async function fetchFrameworks(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      const resp = await complianceApi.listFrameworks()
      frameworks.value = resp.frameworks
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load frameworks'
    } finally {
      isLoading.value = false
    }
  }

  /** Fetch full detail for a specific framework. */
  async function fetchFrameworkDetail(frameworkId: string): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      activeFramework.value = await complianceApi.getFrameworkDetail(frameworkId)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load framework'
    } finally {
      isLoading.value = false
    }
  }

  /** Toggle a framework's enabled state. */
  async function toggleFramework(frameworkId: string, enabled: boolean): Promise<void> {
    error.value = null
    try {
      if (enabled) {
        await complianceApi.enableFramework(frameworkId)
      } else {
        await complianceApi.disableFramework(frameworkId)
      }
      // Update local state
      const fw = frameworks.value.find(f => f.id === frameworkId)
      if (fw) fw.enabled = enabled
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to toggle framework'
    }
  }

  /** Fetch the aggregated compliance dashboard. */
  async function fetchDashboard(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      dashboard.value = await complianceApi.getDashboard()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load dashboard'
    } finally {
      isLoading.value = false
    }
  }

  /** Fetch latest check results. */
  async function fetchLatestResults(framework?: string): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      latestResults.value = await complianceApi.getLatestResults(framework)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load results'
    } finally {
      isLoading.value = false
    }
  }

  /** Fetch violations with pagination. */
  async function fetchViolations(params: {
    framework?: string
    severity?: string
    page?: number
    page_size?: number
  }): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      violations.value = await complianceApi.listViolations(params)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load violations'
    } finally {
      isLoading.value = false
    }
  }

  /** Trigger a compliance check run. */
  async function triggerRun(frameworkId?: string): Promise<void> {
    isRunning.value = true
    error.value = null
    try {
      lastRunResult.value = await complianceApi.runCompliance(frameworkId)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to run compliance checks'
    } finally {
      isRunning.value = false
    }
  }

  /** Configure a control's overrides. */
  async function configureControl(
    controlId: string,
    payload: ConfigureControlRequest,
  ): Promise<void> {
    error.value = null
    try {
      await complianceApi.configureControl(controlId, payload)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to configure control'
    }
  }

  /** Create a custom control. */
  async function createCustomControl(payload: CreateCustomControlRequest): Promise<void> {
    error.value = null
    try {
      await complianceApi.createCustomControl(payload)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to create custom control'
    }
  }

  /** Fetch control check history for trend. */
  async function fetchControlHistory(controlId: string, limit = 90): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      controlHistory.value = await complianceApi.getControlHistory(controlId, limit)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load control history'
    } finally {
      isLoading.value = false
    }
  }

  /** Fetch current schedule configuration. */
  async function fetchSchedule(): Promise<void> {
    error.value = null
    try {
      schedule.value = await complianceApi.getSchedule()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load schedule'
    }
  }

  /** Update schedule configuration. */
  async function updateSchedule(payload: UpdateScheduleRequest): Promise<void> {
    error.value = null
    try {
      schedule.value = await complianceApi.updateSchedule(payload)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update schedule'
    }
  }

  return {
    // State
    frameworks,
    activeFramework,
    dashboard,
    latestResults,
    violations,
    schedule,
    controlHistory,
    lastRunResult,
    isLoading,
    isRunning,
    error,

    // Getters
    enabledFrameworks,
    overallScore,
    totalViolations,

    // Actions
    fetchFrameworks,
    fetchFrameworkDetail,
    toggleFramework,
    fetchDashboard,
    fetchLatestResults,
    fetchViolations,
    triggerRun,
    configureControl,
    createCustomControl,
    fetchControlHistory,
    fetchSchedule,
    updateSchedule,
  }
})
