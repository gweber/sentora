/**
 * Enforcement domain API client.
 *
 * Provides typed async functions for enforcement rule CRUD,
 * check execution, results, summary, and violations.
 */

import client from './client'

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

export interface EnforcementRule {
  id: string
  name: string
  description: string | null
  taxonomy_category_id: string
  type: string
  severity: string
  enabled: boolean
  scope_groups: string[]
  scope_tags: string[]
  labels: string[]
  created_at: string | null
  updated_at: string | null
  created_by: string | null
}

export interface RuleListResponse {
  rules: EnforcementRule[]
  total: number
}

export interface EnforcementViolation {
  agent_id: string
  agent_hostname: string
  violation_detail: string
  app_name: string | null
  app_version: string | null
}

export interface EnforcementResult {
  rule_id: string
  rule_name: string
  rule_type: string
  severity: string
  checked_at: string
  status: string
  total_agents: number
  compliant_agents: number
  non_compliant_agents: number
  violations: EnforcementViolation[]
}

export interface CheckRunResponse {
  run_id: string
  rules_evaluated: number
  passed: number
  failed: number
  total_violations: number
  duration_ms: number
}

export interface SummaryResponse {
  total_rules: number
  enabled_rules: number
  passing: number
  failing: number
  total_violations: number
  by_severity: Record<string, number>
  last_checked_at: string | null
}

export interface ViolationDetail {
  rule_id: string
  rule_name: string
  rule_type: string
  severity: string
  agent_id: string
  agent_hostname: string
  violation_detail: string
  app_name: string | null
  app_version: string | null
  checked_at: string
}

export interface ViolationListResponse {
  violations: ViolationDetail[]
  total: number
  page: number
  page_size: number
}

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export interface CreateRuleRequest {
  name: string
  description?: string
  taxonomy_category_id: string
  type: string
  severity: string
  scope_groups?: string[]
  scope_tags?: string[]
  labels?: string[]
}

export interface UpdateRuleRequest {
  name?: string
  description?: string
  taxonomy_category_id?: string
  type?: string
  severity?: string
  scope_groups?: string[]
  scope_tags?: string[]
  labels?: string[]
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/** List all enforcement rules. */
export async function listRules(): Promise<RuleListResponse> {
  const { data } = await client.get<RuleListResponse>('/enforcement/rules')
  return data
}

/** Create a new enforcement rule. */
export async function createRule(payload: CreateRuleRequest): Promise<EnforcementRule> {
  const { data } = await client.post<EnforcementRule>('/enforcement/rules', payload)
  return data
}

/** Get a single rule by ID. */
export async function getRule(ruleId: string): Promise<EnforcementRule> {
  const { data } = await client.get<EnforcementRule>(`/enforcement/rules/${ruleId}`)
  return data
}

/** Update a rule. */
export async function updateRule(ruleId: string, payload: UpdateRuleRequest): Promise<EnforcementRule> {
  const { data } = await client.put<EnforcementRule>(`/enforcement/rules/${ruleId}`, payload)
  return data
}

/** Delete a rule. */
export async function deleteRule(ruleId: string): Promise<void> {
  await client.delete(`/enforcement/rules/${ruleId}`)
}

/** Toggle a rule's enabled state. */
export async function toggleRule(ruleId: string): Promise<EnforcementRule> {
  const { data } = await client.put<EnforcementRule>(`/enforcement/rules/${ruleId}/toggle`)
  return data
}

/** Run all enabled enforcement checks. */
export async function runAllChecks(): Promise<CheckRunResponse> {
  const { data } = await client.post<CheckRunResponse>('/enforcement/check')
  return data
}

/** Run a single rule check. */
export async function runSingleCheck(ruleId: string): Promise<CheckRunResponse> {
  const { data } = await client.post<CheckRunResponse>(`/enforcement/check/${ruleId}`)
  return data
}

/** Get latest results for all rules. */
export async function getLatestResults(): Promise<EnforcementResult[]> {
  const { data } = await client.get<EnforcementResult[]>('/enforcement/results/latest')
  return data
}

/** Get result history for a rule. */
export async function getRuleHistory(ruleId: string, limit = 90): Promise<EnforcementResult[]> {
  const { data } = await client.get<EnforcementResult[]>(`/enforcement/results/${ruleId}`, { params: { limit } })
  return data
}

/** Get aggregated enforcement summary. */
export async function getSummary(): Promise<SummaryResponse> {
  const { data } = await client.get<SummaryResponse>('/enforcement/summary')
  return data
}

/** Get paginated violations. */
export async function listViolations(params: {
  severity?: string
  page?: number
  page_size?: number
}): Promise<ViolationListResponse> {
  const { data } = await client.get<ViolationListResponse>('/enforcement/violations', { params })
  return data
}
