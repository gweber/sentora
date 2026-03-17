<!--
  Backup Management view — trigger, list, verify, restore, and delete backups.
  Admin-only. Uses /api/v1/admin/ endpoints.
  Backup progress is streamed via WebSocket at /api/v1/admin/backup/progress.
-->
<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue'
import * as adminApi from '@/api/admin'
import type { BackupRecord, BackupProgressEvent } from '@/api/admin'
import { useWebSocket } from '@/composables/useWebSocket'
import { useToast } from '@/composables/useToast'
import { formatDateTime, formatRelativeTime } from '@/utils/formatters'

const toast = useToast()

const backups = ref<BackupRecord[]>([])
const loading = ref(true)
const loaded = ref(false)
const error = ref<string | null>(null)

// Confirm dialog state
const confirmAction = ref<'restore' | 'delete' | null>(null)
const confirmTarget = ref<BackupRecord | null>(null)
const verifyingId = ref<string | null>(null)
const verifyResults = ref<Record<string, boolean | null>>({})
const actionLoading = ref(false)

// ── Backup progress (WebSocket) ──────────────────────────────────────────
const backupRunning = ref(false)
const backupPhase = ref('')
const backupProgress = ref(0)
const backupMessage = ref('')

const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/admin/backup/progress`

function handleWsMessage(data: unknown) {
  const ev = data as BackupProgressEvent
  if (!ev || !ev.type) return

  if (ev.type === 'progress') {
    backupRunning.value = true
    backupPhase.value = ev.phase
    backupProgress.value = ev.progress_percent
    backupMessage.value = ev.message
  } else if (ev.type === 'completed') {
    backupProgress.value = 100
    backupMessage.value = ev.message
    // Briefly show 100% before clearing
    setTimeout(() => {
      backupRunning.value = false
      backupProgress.value = 0
      backupPhase.value = ''
      backupMessage.value = ''
    }, 1500)
    if (ev.record) {
      toast.show(`Backup ${ev.record.id} completed (${formatBytes(ev.record.size_bytes)})`)
    }
    loadBackups()
  } else if (ev.type === 'failed') {
    backupRunning.value = false
    backupProgress.value = 0
    backupPhase.value = ''
    toast.show(ev.message || 'Backup failed', 'error')
    backupMessage.value = ''
    loadBackups()
  }
}

const { connect: wsConnect, disconnect: wsDisconnect } = useWebSocket(wsUrl, handleWsMessage)

// ── Data loading ─────────────────────────────────────────────────────────

async function loadBackups() {
  loading.value = true
  error.value = null
  try {
    const res = await adminApi.listBackups()
    backups.value = res.backups
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load backups'
  } finally {
    loading.value = false
    loaded.value = true
  }
}

async function triggerBackup() {
  if (backupRunning.value || actionLoading.value) return
  actionLoading.value = true
  try {
    await adminApi.triggerBackup()
    // Progress will come via WebSocket
    backupRunning.value = true
    backupPhase.value = 'started'
    backupProgress.value = 5
    backupMessage.value = 'Backup started...'
  } catch (e) {
    toast.show(e instanceof Error ? e.message : 'Failed to start backup', 'error')
  } finally {
    actionLoading.value = false
  }
}

async function verifyBackup(id: string) {
  verifyingId.value = id
  try {
    const res = await adminApi.verifyBackup(id)
    verifyResults.value[id] = res.valid
    toast.show(res.valid ? 'Backup integrity verified' : 'Backup integrity check FAILED', res.valid ? 'success' : 'error')
  } catch (e) {
    verifyResults.value[id] = false
    toast.show(e instanceof Error ? e.message : 'Verification failed', 'error')
  } finally {
    verifyingId.value = null
  }
}

async function handleConfirm() {
  if (!confirmTarget.value || !confirmAction.value) return
  const target = confirmTarget.value
  const action = confirmAction.value
  confirmAction.value = null
  confirmTarget.value = null

  actionLoading.value = true
  try {
    if (action === 'restore') {
      const res = await adminApi.restoreBackup(target.id)
      toast.show(res.message || 'Restore started')
    } else if (action === 'delete') {
      await adminApi.deleteBackup(target.id)
      toast.show(`Backup ${target.id} deleted`)
    }
    await loadBackups()
  } catch (e) {
    toast.show(e instanceof Error ? e.message : `${action} failed`, 'error')
  } finally {
    actionLoading.value = false
  }
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

function statusStyle(s: string): string {
  switch (s) {
    case 'completed': return 'background: var(--success-bg); color: var(--success-text); border: 1px solid var(--success-border);'
    case 'in_progress': return 'background: var(--info-bg); color: var(--info-text);'
    case 'failed': return 'background: var(--error-bg); color: var(--error-text); border: 1px solid var(--error-border);'
    default: return 'background: var(--badge-bg); color: var(--badge-text);'
  }
}

const hasBackups = computed(() => backups.value.length > 0)

onMounted(() => {
  loadBackups()
  wsConnect()
})

onUnmounted(() => {
  wsDisconnect()
})
</script>

<template>
  <div class="max-w-[900px] mx-auto px-4 py-6 space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-[18px] font-semibold" style="color: var(--heading);">Backup Management</h1>
        <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Create, verify, restore, and manage database backups</p>
      </div>
      <button
        class="px-4 py-2 rounded-lg text-white text-[13px] font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
        style="background: var(--brand-primary);"
        :disabled="backupRunning || actionLoading"
        @click="triggerBackup"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
        </svg>
        {{ backupRunning ? 'Backup Running...' : 'Create Backup' }}
      </button>
    </div>

    <!-- Progress bar (shown during backup) -->
    <div v-if="backupRunning" class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
      <div class="px-5 py-4">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2">
            <svg v-if="backupPhase === 'dumping' || backupPhase === 'finalising'" class="w-4 h-4 animate-spin shrink-0" style="color: var(--brand-primary);" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span class="text-[13px] font-medium" style="color: var(--text-1);">{{ backupMessage || 'Backup in progress...' }}</span>
          </div>
          <span class="text-[12px] font-mono font-semibold" style="color: var(--brand-primary);">{{ backupProgress }}%</span>
        </div>
        <div class="w-full h-2 rounded-full overflow-hidden" style="background: var(--surface-inset);">
          <div
            class="h-full rounded-full transition-all duration-500 ease-out"
            style="background: var(--brand-primary);"
            :style="{ width: backupProgress + '%' }"
          ></div>
        </div>
        <div class="flex items-center gap-2 mt-2">
          <span class="text-[11px] font-medium px-2 py-0.5 rounded-full" style="background: var(--info-bg); color: var(--info-text);">
            {{ backupPhase }}
          </span>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="rounded-xl px-5 py-4" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);">
      <p class="text-[13px] font-medium">{{ error }}</p>
    </div>

    <!-- Loading -->
    <div v-if="loading && !loaded" class="space-y-3">
      <div v-for="i in 3" :key="i" class="skeleton h-16 rounded-xl"></div>
    </div>

    <!-- Empty state -->
    <div v-else-if="loaded && !hasBackups && !backupRunning" class="rounded-xl px-8 py-12 text-center" style="background: var(--surface); border: 1px solid var(--border);">
      <svg class="w-12 h-12 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" style="color: var(--text-3);">
        <path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
      </svg>
      <p class="text-[14px] font-medium" style="color: var(--text-2);">No backups yet</p>
      <p class="text-[12px] mt-1" style="color: var(--text-3);">Create your first backup to protect your data</p>
    </div>

    <!-- Backup list -->
    <div v-else-if="hasBackups" class="space-y-2">
      <div
        v-for="backup in backups" :key="backup.id"
        class="rounded-xl px-5 py-4 flex items-center gap-4"
        style="background: var(--surface); border: 1px solid var(--border);"
      >
        <!-- Status icon -->
        <div class="w-10 h-10 rounded-full flex items-center justify-center shrink-0"
          :style="backup.status === 'completed' ? 'background: var(--success-bg); color: var(--success-text);' : backup.status === 'failed' ? 'background: var(--error-bg); color: var(--error-text);' : 'background: var(--info-bg); color: var(--info-text);'">
          <svg v-if="backup.status === 'completed'" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>
          <svg v-else-if="backup.status === 'failed'" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          <svg v-else class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
        </div>

        <!-- Info -->
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <span class="text-[13px] font-semibold font-mono" style="color: var(--text-1);">{{ backup.id }}</span>
            <span class="text-[10px] font-medium px-1.5 py-0.5 rounded-full" :style="statusStyle(backup.status)">{{ backup.status }}</span>
            <span v-if="verifyResults[backup.id] === true" class="text-[10px] font-medium px-1.5 py-0.5 rounded-full" style="background: var(--success-bg); color: var(--success-text);">Verified</span>
            <span v-else-if="verifyResults[backup.id] === false" class="text-[10px] font-medium px-1.5 py-0.5 rounded-full" style="background: var(--error-bg); color: var(--error-text);">Corrupt</span>
          </div>
          <div class="flex items-center gap-3 mt-0.5 text-[11px]" style="color: var(--text-3);">
            <span>{{ formatDateTime(backup.timestamp) }}</span>
            <span>{{ formatRelativeTime(backup.timestamp) }}</span>
            <span v-if="backup.size_bytes">{{ formatBytes(backup.size_bytes) }}</span>
            <span v-if="backup.duration_seconds">{{ backup.duration_seconds.toFixed(1) }}s</span>
          </div>
          <p v-if="backup.error" class="text-[11px] mt-0.5" style="color: var(--error-text);">{{ backup.error }}</p>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-2 shrink-0">
          <button
            v-if="backup.status === 'completed'"
            class="px-3 py-1.5 rounded-lg text-[11px] font-medium transition-colors"
            style="background: var(--surface-hover); color: var(--text-2); border: 1px solid var(--border);"
            :disabled="verifyingId === backup.id"
            @click="verifyBackup(backup.id)"
          >
            {{ verifyingId === backup.id ? 'Checking...' : 'Verify' }}
          </button>
          <button
            v-if="backup.status === 'completed'"
            class="px-3 py-1.5 rounded-lg text-[11px] font-medium transition-colors"
            style="background: var(--warn-bg); color: var(--warn-text); border: 1px solid var(--warn-border);"
            :disabled="actionLoading"
            @click="confirmAction = 'restore'; confirmTarget = backup"
          >Restore</button>
          <button
            class="px-3 py-1.5 rounded-lg text-[11px] font-medium transition-colors"
            style="background: var(--error-bg); color: var(--error-text); border: 1px solid var(--error-border);"
            :disabled="actionLoading"
            @click="confirmAction = 'delete'; confirmTarget = backup"
          >Delete</button>
        </div>
      </div>
    </div>

    <!-- Confirm dialog -->
    <Teleport to="body">
      <div v-if="confirmAction && confirmTarget" class="fixed inset-0 z-50 flex items-center justify-center" style="background: rgba(0,0,0,0.4);" @click.self="confirmAction = null">
        <div class="rounded-xl p-6 w-full max-w-md shadow-xl" style="background: var(--surface); border: 1px solid var(--border);" role="dialog" aria-modal="true">
          <h3 class="text-[15px] font-semibold" style="color: var(--heading);">
            {{ confirmAction === 'restore' ? 'Restore from Backup' : 'Delete Backup' }}
          </h3>
          <p class="text-[13px] mt-2" style="color: var(--text-2);">
            <template v-if="confirmAction === 'restore'">
              This will restore the database to the state captured in backup
              <strong class="font-mono">{{ confirmTarget.id }}</strong>.
              <span class="font-semibold" style="color: var(--error-text);">All current data will be overwritten.</span>
            </template>
            <template v-else>
              Permanently delete backup <strong class="font-mono">{{ confirmTarget.id }}</strong>? This cannot be undone.
            </template>
          </p>
          <div class="flex justify-end gap-3 mt-5">
            <button class="px-4 py-2 rounded-lg text-[13px] font-medium" style="color: var(--text-2);" @click="confirmAction = null">Cancel</button>
            <button
              class="px-4 py-2 rounded-lg text-white text-[13px] font-medium"
              :style="confirmAction === 'restore' ? 'background: var(--warn-text);' : 'background: var(--error-text);'"
              @click="handleConfirm"
            >
              {{ confirmAction === 'restore' ? 'Restore Now' : 'Delete' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
