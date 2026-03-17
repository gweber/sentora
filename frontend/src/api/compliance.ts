/**
 * Compliance domain API client.
 *
 * Provides typed async functions for all compliance endpoints.
 * Covers framework management, control configuration, check execution,
 * results, dashboard, violations, and scheduling.
 */

import client from './client'

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

export interface FrameworkSummary {
  id: string
  name: string
  version: string
  description: string
  disclaimer: string
  enabled: boolean
  total_controls: number
  enabled_controls: number
}

export interface FrameworkListResponse {
  frameworks: FrameworkSummary[]
}

export interface ControlResponse {
  id: string
  framework_id: string
  name: string
  description: string
  category: string
  severity: string
  check_type: string
  parameters: Record<string, unknown>
  scope_tags: string[]
  scope_groups: string[]
  enabled: boolean
  disable_reason: string | null
  hipaa_type: string | null
  bsi_level: string | null
  remediation: string
  is_custom: boolean
}

export interface FrameworkDetailResponse {
  id: string
  name: string
  version: string
  description: string
  disclaimer: string
  enabled: boolean
  controls: ControlResponse[]
}

export interface ViolationResponse {
  agent_id: string
  agent_hostname: string
  violation_detail: string
  app_name: string | null
  app_version: string | null
  remediation: string
}

export interface CheckResultResponse {
  control_id: string
  framework_id: string
  control_name: string
  category: string
  severity: string
  status: string
  checked_at: string
  total_endpoints: number
  compliant_endpoints: number
  non_compliant_endpoints: number
  evidence_summary: string
  violations: ViolationResponse[]
}

export interface LatestResultsResponse {
  results: CheckResultResponse[]
  total: number
  checked_at: string | null
}

export interface ControlHistoryEntry {
  status: string
  checked_at: string
  total_endpoints: number
  compliant_endpoints: number
  non_compliant_endpoints: number
  evidence_summary: string
}

export interface ControlHistoryResponse {
  control_id: string
  framework_id: string
  entries: ControlHistoryEntry[]
  total: number
}

export interface FrameworkScoreResponse {
  framework_id: string
  framework_name: string
  total_controls: number
  passed: number
  failed: number
  warning: number
  error: number
  not_applicable: number
  score_percent: number
}

export interface DashboardResponse {
  frameworks: FrameworkScoreResponse[]
  overall_score_percent: number
  total_violations: number
  last_run_at: string | null
}

export interface ViolationDetailResponse {
  control_id: string
  framework_id: string
  control_name: string
  severity: string
  agent_id: string
  agent_hostname: string
  violation_detail: string
  app_name: string | null
  app_version: string | null
  remediation: string
  checked_at: string
}

export interface ViolationListResponse {
  violations: ViolationDetailResponse[]
  total: number
  page: number
  page_size: number
}

export interface RunResultResponse {
  run_id: string
  status: string
  controls_evaluated: number
  passed: number
  failed: number
  warning: number
  duration_ms: number
}

export interface ScheduleResponse {
  run_after_sync: boolean
  cron_expression: string | null
  enabled: boolean
  updated_at: string | null
  updated_by: string | null
}

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export interface ConfigureControlRequest {
  enabled?: boolean | null
  disable_reason?: string | null
  severity_override?: string | null
  parameters_override?: Record<string, unknown> | null
  scope_tags_override?: string[] | null
  scope_groups_override?: string[] | null
}

export interface CreateCustomControlRequest {
  id: string
  framework_id: string
  name: string
  description: string
  category: string
  severity: string
  check_type: string
  parameters?: Record<string, unknown>
  scope_tags?: string[]
  scope_groups?: string[]
  remediation?: string
}

export interface UpdateScheduleRequest {
  run_after_sync?: boolean | null
  cron_expression?: string | null
  enabled?: boolean | null
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/** List all available compliance frameworks. */
export async function listFrameworks(): Promise<FrameworkListResponse> {
  const { data } = await client.get<FrameworkListResponse>('/compliance/frameworks')
  return data
}

/** Get full framework detail including all controls. */
export async function getFrameworkDetail(frameworkId: string): Promise<FrameworkDetailResponse> {
  const { data } = await client.get<FrameworkDetailResponse>(`/compliance/frameworks/${frameworkId}`)
  return data
}

/** Enable a compliance framework. */
export async function enableFramework(frameworkId: string): Promise<void> {
  await client.put(`/compliance/frameworks/${frameworkId}/enable`)
}

/** Disable a compliance framework. */
export async function disableFramework(frameworkId: string): Promise<void> {
  await client.put(`/compliance/frameworks/${frameworkId}/disable`)
}

/** Configure a control's tenant-specific overrides. */
export async function configureControl(
  controlId: string,
  payload: ConfigureControlRequest,
): Promise<ControlResponse> {
  const { data } = await client.put<ControlResponse>(`/compliance/controls/${controlId}`, payload)
  return data
}

/** Create a tenant-specific custom control. */
export async function createCustomControl(
  payload: CreateCustomControlRequest,
): Promise<ControlResponse> {
  const { data } = await client.post<ControlResponse>('/compliance/controls/custom', payload)
  return data
}

/** Trigger a compliance check run. */
export async function runCompliance(frameworkId?: string): Promise<RunResultResponse> {
  const body = frameworkId ? { framework_id: frameworkId } : {}
  const { data } = await client.post<RunResultResponse>('/compliance/run', body)
  return data
}

/** Get the latest check results for all active controls. */
export async function getLatestResults(framework?: string): Promise<LatestResultsResponse> {
  const params: Record<string, string> = {}
  if (framework) params.framework = framework
  const { data } = await client.get<LatestResultsResponse>('/compliance/results/latest', { params })
  return data
}

/** Get historical check results for a control. */
export async function getControlHistory(
  controlId: string,
  limit = 90,
): Promise<ControlHistoryResponse> {
  const { data } = await client.get<ControlHistoryResponse>(
    `/compliance/results/${controlId}/history`,
    { params: { limit } },
  )
  return data
}

/** Get the aggregated compliance dashboard. */
export async function getDashboard(): Promise<DashboardResponse> {
  const { data } = await client.get<DashboardResponse>('/compliance/dashboard')
  return data
}

/** Get paginated violations. */
export async function listViolations(params: {
  framework?: string
  severity?: string
  page?: number
  page_size?: number
}): Promise<ViolationListResponse> {
  const { data } = await client.get<ViolationListResponse>('/compliance/violations', { params })
  return data
}

/** Unified violation from compliance or enforcement. */
export interface UnifiedViolation {
  source: string
  control_id: string
  control_name: string
  framework_id: string
  severity: string
  agent_id: string
  agent_hostname: string
  violation_detail: string
  app_name: string | null
  app_version: string | null
  remediation: string
  checked_at: string
}

/** Unified violations response. */
export interface UnifiedViolationListResponse {
  violations: UnifiedViolation[]
  total: number
  page: number
  page_size: number
}

/** Get unified violations from both compliance and enforcement. */
export async function listUnifiedViolations(params: {
  source?: string
  severity?: string
  page?: number
  page_size?: number
}): Promise<UnifiedViolationListResponse> {
  const { data } = await client.get<UnifiedViolationListResponse>(
    '/compliance/violations/unified',
    { params },
  )
  return data
}

/** Download violations export CSV via authenticated client. */
export async function downloadViolationsExport(frameworkId?: string): Promise<Blob> {
  const params: Record<string, string> = { format: 'csv' }
  if (frameworkId) params.framework_id = frameworkId
  const { data } = await client.get('/compliance/violations/export', {
    params,
    responseType: 'blob',
  })
  return data as Blob
}

/** Get current compliance check schedule. */
export async function getSchedule(): Promise<ScheduleResponse> {
  const { data } = await client.get<ScheduleResponse>('/compliance/schedule')
  return data
}

/** Update compliance check schedule. */
export async function updateSchedule(payload: UpdateScheduleRequest): Promise<ScheduleResponse> {
  const { data } = await client.put<ScheduleResponse>('/compliance/schedule', payload)
  return data
}
