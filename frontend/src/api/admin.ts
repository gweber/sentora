/**
 * Admin API — backup management and system operations.
 */
import client from './client'

export interface BackupRecord {
  id: string
  timestamp: string
  size_bytes: number
  checksum_sha256: string
  storage_type: string
  storage_path: string
  status: string
  triggered_by: string
  duration_seconds: number
  error: string | null
}

export interface BackupListResponse {
  backups: BackupRecord[]
  total: number
}

export interface BackupStartedResponse {
  backup_id: string
  status: string
  message: string
}

export interface BackupProgressEvent {
  type: 'progress' | 'completed' | 'failed'
  backup_id: string
  phase: string
  progress_percent: number
  message: string
  record?: BackupRecord
}

export interface RestoreResponse {
  status: string
  message: string
}

/** Trigger a new backup (returns immediately, progress via WebSocket). */
export async function triggerBackup(): Promise<BackupStartedResponse> {
  const { data } = await client.post<BackupStartedResponse>('/admin/backup')
  return data
}

/** List all backups. */
export async function listBackups(): Promise<BackupListResponse> {
  const { data } = await client.get<BackupListResponse>('/admin/backups')
  return data
}

/** Get a single backup by ID. */
export async function getBackup(id: string): Promise<BackupRecord> {
  const { data } = await client.get<BackupRecord>(`/admin/backups/${id}`)
  return data
}

/** Restore from a backup. */
export async function restoreBackup(backupId: string): Promise<RestoreResponse> {
  const { data } = await client.post<RestoreResponse>('/admin/restore', { backup_id: backupId })
  return data
}

/** Verify a backup's integrity (checksum). */
export async function verifyBackup(backupId: string): Promise<{ valid: boolean }> {
  const { data } = await client.post<{ valid: boolean }>(`/admin/backups/${backupId}/verify`)
  return data
}

/** Delete a backup. */
export async function deleteBackup(backupId: string): Promise<void> {
  await client.delete(`/admin/backups/${backupId}`)
}
