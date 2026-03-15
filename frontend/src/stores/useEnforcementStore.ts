/**
 * Pinia store for enforcement domain state management.
 *
 * Manages enforcement rules, check results, summary, and violations.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as enforcementApi from '@/api/enforcement'
import type {
  EnforcementRule,
  EnforcementResult,
  SummaryResponse,
  ViolationListResponse,
  CheckRunResponse,
  CreateRuleRequest,
  UpdateRuleRequest,
} from '@/api/enforcement'

export const useEnforcementStore = defineStore('enforcement', () => {
  // ── State ──────────────────────────────────────────────────────────
  const rules = ref<EnforcementRule[]>([])
  const latestResults = ref<EnforcementResult[]>([])
  const summary = ref<SummaryResponse | null>(null)
  const violations = ref<ViolationListResponse | null>(null)
  const lastRunResult = ref<CheckRunResponse | null>(null)

  const isLoading = ref(false)
  const isRunning = ref(false)
  const error = ref<string | null>(null)

  // ── Getters ────────────────────────────────────────────────────────

  /** Rules that are enabled. */
  const enabledRules = computed(() => rules.value.filter(r => r.enabled))

  /** Total violation count from summary. */
  const totalViolations = computed(() => summary.value?.total_violations ?? 0)

  // ── Actions ────────────────────────────────────────────────────────

  /** Fetch all rules. */
  async function fetchRules(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      const resp = await enforcementApi.listRules()
      rules.value = resp.rules
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load rules'
    } finally {
      isLoading.value = false
    }
  }

  /** Create a new rule. */
  async function createRule(payload: CreateRuleRequest): Promise<void> {
    error.value = null
    try {
      const rule = await enforcementApi.createRule(payload)
      rules.value.unshift(rule)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to create rule'
    }
  }

  /** Update a rule. */
  async function updateRule(ruleId: string, payload: UpdateRuleRequest): Promise<void> {
    error.value = null
    try {
      const updated = await enforcementApi.updateRule(ruleId, payload)
      const idx = rules.value.findIndex(r => r.id === ruleId)
      if (idx !== -1) rules.value[idx] = updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update rule'
    }
  }

  /** Delete a rule. */
  async function deleteRule(ruleId: string): Promise<void> {
    error.value = null
    try {
      await enforcementApi.deleteRule(ruleId)
      rules.value = rules.value.filter(r => r.id !== ruleId)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to delete rule'
    }
  }

  /** Toggle a rule's enabled state. */
  async function toggleRule(ruleId: string): Promise<void> {
    error.value = null
    try {
      const updated = await enforcementApi.toggleRule(ruleId)
      const idx = rules.value.findIndex(r => r.id === ruleId)
      if (idx !== -1) rules.value[idx] = updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to toggle rule'
    }
  }

  /** Fetch summary data. */
  async function fetchSummary(): Promise<void> {
    error.value = null
    try {
      summary.value = await enforcementApi.getSummary()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load summary'
    }
  }

  /** Fetch latest results. */
  async function fetchLatestResults(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      latestResults.value = await enforcementApi.getLatestResults()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load results'
    } finally {
      isLoading.value = false
    }
  }

  /** Fetch violations. */
  async function fetchViolations(params: {
    severity?: string
    page?: number
    page_size?: number
  }): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      violations.value = await enforcementApi.listViolations(params)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load violations'
    } finally {
      isLoading.value = false
    }
  }

  /** Trigger enforcement checks. */
  async function triggerRun(): Promise<void> {
    isRunning.value = true
    error.value = null
    try {
      lastRunResult.value = await enforcementApi.runAllChecks()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to run checks'
    } finally {
      isRunning.value = false
    }
  }

  return {
    rules,
    latestResults,
    summary,
    violations,
    lastRunResult,
    isLoading,
    isRunning,
    error,
    enabledRules,
    totalViolations,
    fetchRules,
    createRule,
    updateRule,
    deleteRule,
    toggleRule,
    fetchSummary,
    fetchLatestResults,
    fetchViolations,
    triggerRun,
  }
})
