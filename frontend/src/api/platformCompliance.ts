/**
 * Platform compliance API client.
 *
 * Sentora's own security posture evaluation — SOC 2 and ISO 27001
 * platform-level controls (RBAC, audit logs, backups, MFA).
 */

import client from './client'

export interface PlatformControl {
  control_id: string
  framework: string
  reference: string
  title: string
  category: string
  status: 'passing' | 'warning' | 'failing' | 'not_applicable'
  evidence_summary: string
  evidence_count: number
  last_checked: string
}

export interface PlatformDashboard {
  framework: string
  total_controls: number
  passing: number
  warning: number
  failing: number
  not_applicable: number
  score_percent: number
  controls: PlatformControl[]
}

export interface PlatformReport {
  id: string
  framework: string
  generated_at: string
  generated_by: string
  period_start: string
  period_end: string
  status: string
  total_controls: number
  passing_controls: number
  warning_controls: number
  failing_controls: number
}

export interface PlatformReportDetail extends PlatformReport {
  controls: PlatformControl[]
}

/** Fetch live platform compliance posture. */
export async function getDashboard(framework: string): Promise<PlatformDashboard> {
  const { data } = await client.get<PlatformDashboard>(
    `/compliance/platform/dashboard/${framework}`,
  )
  return data
}

/** Generate a platform compliance report snapshot. */
export async function generateReport(
  framework: string,
  periodDays = 90,
): Promise<PlatformReport> {
  const { data } = await client.post<PlatformReport>(
    '/compliance/platform/reports',
    { framework, period_days: periodDays },
  )
  return data
}

/** List generated platform reports. */
export async function listReports(
  framework?: string,
): Promise<{ reports: PlatformReport[]; total: number }> {
  const params: Record<string, string> = {}
  if (framework) params.framework = framework
  const { data } = await client.get<{ reports: PlatformReport[]; total: number }>(
    '/compliance/platform/reports',
    { params },
  )
  return data
}

/** Get a platform report with full control details. */
export async function getReport(id: string): Promise<PlatformReportDetail> {
  const { data } = await client.get<PlatformReportDetail>(
    `/compliance/platform/reports/${id}`,
  )
  return data
}

/** Delete a platform report. */
export async function deleteReport(id: string): Promise<void> {
  await client.delete(`/compliance/platform/reports/${id}`)
}

/** Download CSV for a platform report via authenticated client. */
export async function downloadReportCsv(id: string): Promise<Blob> {
  const { data } = await client.get(`/compliance/platform/reports/${id}/csv`, {
    responseType: 'blob',
  })
  return data as Blob
}
