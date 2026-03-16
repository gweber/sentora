/** Webhook domain types — mirrors backend DTOs. */

export interface Webhook {
  id: string
  name: string
  url: string
  events: string[]
  enabled: boolean
  created_at: string
  last_triggered_at: string | null
  failure_count: number
  last_error: string | null
}

export interface WebhookCreateRequest {
  name: string
  url: string
  events: string[]
  secret?: string
}

export interface WebhookUpdateRequest {
  name?: string
  url?: string
  events?: string[]
  enabled?: boolean
}

export interface WebhookTestResponse {
  success: boolean
  status_code: number | null
  response_time_ms: number
}

/** Available webhook event types — must match backend VALID_EVENTS. */
export const WEBHOOK_EVENTS = [
  'sync.completed',
  'sync.failed',
  'classification.completed',
  'classification.anomaly_detected',
  'enforcement.check.completed',
  'enforcement.violation.new',
  'enforcement.violation.resolved',
  'compliance.check.completed',
  'compliance.violation.new',
  'compliance.violation.resolved',
  'compliance.score.degraded',
  'audit.chain.integrity_failure',
] as const

export type WebhookEvent = (typeof WEBHOOK_EVENTS)[number]
