<!--
  LibrarySourcesView — admin page for managing fingerprint library ingestion sources.
  Shows source cards with last run status, live progress bar via WebSocket,
  and ingestion history table.
-->
<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import * as libraryApi from '@/api/library'
import * as configApi from '@/api/config'
import { useWebSocket } from '@/composables/useWebSocket'
import type { SourceInfo, IngestionRunResponse, IngestionProgressMessage } from '@/types/library'

// ── State ─────────────────────────────────────────────────────────────────────

const sources = ref<SourceInfo[]>([])
const runs = ref<IngestionRunResponse[]>([])
const runsTotal = ref(0)
const isLoading = ref(true)
const error = ref<string | null>(null)
const triggeringSource = ref<string | null>(null)
const triggerError = ref<string | null>(null)

// History filter
const historySourceFilter = ref('')

// NVD API Key
const nvdApiKey = ref('')
const nvdApiKeySet = ref(false)
const nvdSaving = ref(false)
const nvdSaveStatus = ref<'idle' | 'saved' | 'error'>('idle')
let _nvdSaveTimer: ReturnType<typeof setTimeout> | null = null

// Live progress from WebSocket (keyed by source name)
const liveProgress = ref<Record<string, IngestionProgressMessage>>({})

// ── WebSocket ─────────────────────────────────────────────────────────────────

const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/library/sources/progress`

const { connect: wsConnect, disconnect: wsDisconnect } = useWebSocket(
  wsUrl,
  (data: unknown) => {
    const msg = data as IngestionProgressMessage
    if (!msg.source) return
    liveProgress.value = { ...liveProgress.value, [msg.source]: msg }

    // On terminal events (per-source or global), reload data and clear progress
    if (['completed', 'failed', 'source_completed', 'source_failed', 'source_cancelled'].includes(msg.type)) {
      loadAll()
      setTimeout(() => {
        const current = { ...liveProgress.value }
        delete current[msg.source]
        liveProgress.value = current
      }, 3000)
    }
  },
)

// ── Data loading ──────────────────────────────────────────────────────────────

async function loadSources() {
  try {
    const res = await libraryApi.listSources()
    sources.value = res.sources
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load sources'
  }
}

async function loadRuns() {
  try {
    const res = await libraryApi.listIngestionRuns(historySourceFilter.value || undefined)
    runs.value = res.runs
    runsTotal.value = res.total
  } catch {
    // Non-critical — silently ignore
  }
}

async function loadNvdKeyStatus() {
  try {
    const cfg = await configApi.getConfig()
    nvdApiKeySet.value = cfg.nvd_api_key_set
  } catch {
    // non-critical
  }
}

async function saveNvdApiKey() {
  if (!nvdApiKey.value.trim()) return
  nvdSaving.value = true
  nvdSaveStatus.value = 'idle'
  try {
    await configApi.updateConfig({ nvd_api_key: nvdApiKey.value.trim() })
    nvdApiKeySet.value = true
    nvdApiKey.value = ''
    nvdSaveStatus.value = 'saved'
    if (_nvdSaveTimer) clearTimeout(_nvdSaveTimer)
    _nvdSaveTimer = setTimeout(() => { nvdSaveStatus.value = 'idle' }, 3000)
  } catch {
    nvdSaveStatus.value = 'error'
    if (_nvdSaveTimer) clearTimeout(_nvdSaveTimer)
    _nvdSaveTimer = setTimeout(() => { nvdSaveStatus.value = 'idle' }, 5000)
  } finally {
    nvdSaving.value = false
  }
}

async function clearNvdApiKey() {
  nvdSaving.value = true
  try {
    await configApi.updateConfig({ nvd_api_key: '' })
    nvdApiKeySet.value = false
    nvdSaveStatus.value = 'saved'
    if (_nvdSaveTimer) clearTimeout(_nvdSaveTimer)
    _nvdSaveTimer = setTimeout(() => { nvdSaveStatus.value = 'idle' }, 3000)
  } catch {
    nvdSaveStatus.value = 'error'
  } finally {
    nvdSaving.value = false
  }
}

async function loadAll() {
  isLoading.value = true
  error.value = null
  await Promise.all([loadSources(), loadRuns(), loadNvdKeyStatus()])
  isLoading.value = false
}

onMounted(() => {
  loadAll()
  wsConnect()
})

onUnmounted(() => {
  wsDisconnect()
  if (_nvdSaveTimer) clearTimeout(_nvdSaveTimer)
})

// ── Computed ──────────────────────────────────────────────────────────────────

const sourceFilterOptions = computed(() => {
  return [
    { key: '', label: 'All Sources' },
    ...sources.value.map((s) => ({ key: s.name, label: sourceDisplayName(s.name) })),
  ]
})

// ── Helpers ───────────────────────────────────────────────────────────────────

function sourceDisplayName(name: string): string {
  const map: Record<string, string> = {
    nist_cpe: 'NIST CPE',
    mitre: 'MITRE ATT&CK',
    chocolatey: 'Chocolatey',
    homebrew: 'Homebrew',
    homebrew_cask: 'Homebrew Cask',
  }
  return map[name] ?? name
}

function sourceIcon(name: string): string {
  switch (name) {
    case 'nist_cpe': return 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z'
    case 'mitre': return 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z'
    case 'chocolatey': return 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4'
    case 'homebrew': return 'M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z'
    case 'homebrew_cask': return 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z'
    default: return 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4'
  }
}

function sourceBadgeClass(name: string): string {
  switch (name) {
    case 'nist_cpe': return 'bg-blue-500/10 text-blue-600 border-blue-200'
    case 'mitre': return 'bg-purple-500/10 text-purple-600 border-purple-200'
    case 'chocolatey': return 'bg-amber-500/10 text-amber-600 border-amber-200'
    case 'homebrew': return 'bg-emerald-500/10 text-emerald-600 border-emerald-200'
    case 'homebrew_cask': return 'bg-teal-500/10 text-teal-600 border-teal-200'
    default: return 'bg-slate-500/10 text-muted border-muted'
  }
}

function runStatusBadgeClass(status: string): string {
  switch (status) {
    case 'completed': return 'bg-emerald-50 text-emerald-700 border-emerald-200'
    case 'running': return 'bg-blue-50 text-blue-700 border-blue-200'
    case 'failed': return 'bg-red-50 text-red-600 border-red-200'
    case 'cancelled': return 'bg-amber-50 text-amber-700 border-amber-200'
    default: return 'badge-neutral border'
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return 'Never'
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function timeAgo(iso: string | null): string {
  if (!iso) return 'Never'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

/** Check whether a source has live progress data from the WebSocket. */
function hasLiveProgress(name: string): boolean {
  return name in liveProgress.value
}

/** Get live progress for a source, or null if none. */
function getProgress(name: string): IngestionProgressMessage | null {
  return liveProgress.value[name] ?? null
}

// ── Actions ───────────────────────────────────────────────────────────────────

async function handleTriggerIngestion(source: string) {
  triggeringSource.value = source
  triggerError.value = null
  try {
    await libraryApi.triggerIngestion(source)
    await loadAll()
  } catch (e) {
    triggerError.value = e instanceof Error ? e.message : `Failed to trigger ingestion for ${source}`
  } finally {
    triggeringSource.value = null
  }
}

async function handleResumeIngestion(source: string) {
  triggeringSource.value = source
  triggerError.value = null
  try {
    await libraryApi.resumeIngestion(source)
    await loadAll()
  } catch (e) {
    triggerError.value = e instanceof Error ? e.message : `Failed to resume ingestion for ${source}`
  } finally {
    triggeringSource.value = null
  }
}

async function handleCancelIngestion(source: string) {
  triggerError.value = null
  try {
    await libraryApi.cancelIngestion(source)
  } catch (e) {
    triggerError.value = e instanceof Error ? e.message : `Failed to cancel ingestion for ${source}`
  }
}

function filterHistory(source: string) {
  historySourceFilter.value = source
  loadRuns()
}
</script>

<template>
  <div class="p-6 max-w-[1100px] space-y-6">

    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <div class="flex items-center gap-2 mb-1">
          <router-link
            to="/library"
            class="text-[12px] hover:text-indigo-600 transition-colors no-underline"
            style="color: var(--text-3);"
            aria-label="Back to library browser"
          >Library</router-link>
          <span class="text-[12px] text-slate-300">/</span>
          <span class="text-[12px]" style="color: var(--text-3);">Sources</span>
        </div>
        <h1 class="text-[20px] font-bold" style="color: var(--heading);">Library Sources</h1>
        <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Manage fingerprint library ingestion adapters</p>
      </div>
    </div>

    <!-- NVD API Key -->
    <div class="rounded-xl border px-5 py-4" style="background: var(--surface); border-color: var(--border);">
      <div class="flex items-start gap-3">
        <div class="shrink-0 w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center mt-0.5">
          <svg class="w-4 h-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <h3 class="text-[14px] font-semibold" style="color: var(--heading);">NVD API Key</h3>
            <span
              v-if="nvdApiKeySet"
              class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200"
            >Configured</span>
            <span
              v-else
              class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-200"
            >Not set</span>
          </div>
          <p class="text-[12px] mb-3" style="color: var(--text-3);">
            Speeds up NIST CPE ingestion by 10x. Free at
            <a href="https://nvd.nist.gov/developers/request-an-api-key" target="_blank" rel="noopener" class="text-indigo-600 hover:underline">nvd.nist.gov</a>.
          </p>
          <div class="flex items-center gap-2">
            <template v-if="!nvdApiKeySet">
              <input
                v-model="nvdApiKey"
                type="password"
                placeholder="Paste your NVD API key"
                class="flex-1 max-w-xs px-3 py-1.5 rounded-lg border text-[13px] focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400"
                style="background: var(--surface); border-color: var(--border); color: var(--text-1);"
              />
              <button
                :disabled="!nvdApiKey.trim() || nvdSaving"
                class="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-[12px] font-medium hover:bg-indigo-700 transition-colors disabled:opacity-40"
                @click="saveNvdApiKey"
              >{{ nvdSaving ? 'Saving…' : 'Save' }}</button>
            </template>
            <template v-else>
              <span class="text-[12px]" style="color: var(--text-3);">API key is stored securely.</span>
              <button
                :disabled="nvdSaving"
                class="px-3 py-1.5 rounded-lg text-[12px] font-medium border transition-colors hover:border-red-400 hover:text-red-600"
                style="border-color: var(--border); color: var(--text-3);"
                @click="clearNvdApiKey"
              >Remove</button>
            </template>
            <span v-if="nvdSaveStatus === 'saved'" class="text-[11px] text-emerald-600">Saved</span>
            <span v-if="nvdSaveStatus === 'error'" class="text-[11px] text-red-500">Failed to save</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="flex items-center gap-2 text-[13px] py-10 justify-center" style="color: var(--text-3);">
      <svg class="w-4 h-4 animate-spin text-indigo-400" fill="none" viewBox="0 0 24 24" aria-hidden="true">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
      </svg>
      Loading sources...
    </div>

    <!-- Error -->
    <div v-else-if="error" class="text-[13px] rounded-xl px-5 py-4" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
      {{ error }}
    </div>

    <template v-else>

      <!-- Trigger error -->
      <div v-if="triggerError" class="text-[13px] rounded-xl px-5 py-4" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
        {{ triggerError }}
      </div>

      <!-- Source cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4" aria-label="Ingestion sources">
        <div
          v-for="source in sources"
          :key="source.name"
          class="rounded-xl shadow-sm p-5"
          style="background: var(--surface); border: 1px solid var(--border);"
        >
          <!-- Icon + name -->
          <div class="flex items-start gap-3 mb-3">
            <div
              class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border"
              :class="sourceBadgeClass(source.name)"
            >
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" :d="sourceIcon(source.name)" />
              </svg>
            </div>
            <div class="min-w-0 flex-1">
              <h3 class="text-[14px] font-semibold" style="color: var(--text-1);">{{ sourceDisplayName(source.name) }}</h3>
              <p class="text-[12px] mt-0.5 leading-relaxed" style="color: var(--text-3);">{{ source.description }}</p>
            </div>
          </div>

          <!-- Live progress bar -->
          <div v-if="hasLiveProgress(source.name)" class="mb-4">
            <div class="flex items-center gap-2 text-[11px] mb-1.5">
              <svg class="w-3.5 h-3.5 animate-spin text-indigo-500" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
              </svg>
              <span class="font-medium" style="color: var(--text-2);">
                {{ getProgress(source.name)?.message || 'Running...' }}
              </span>
            </div>
            <!-- Progress bar -->
            <div class="w-full h-1.5 rounded-full overflow-hidden" style="background: var(--border-light);">
              <div
                class="h-full rounded-full transition-all duration-500 ease-out"
                :class="getProgress(source.name)?.type === 'failed' ? 'bg-red-500' : getProgress(source.name)?.type === 'completed' ? 'bg-emerald-500' : 'bg-indigo-500'"
                :style="{ width: getProgress(source.name)?.type === 'completed' ? '100%' : 'auto', minWidth: '8px' }"
              >
                <!-- Indeterminate animation for running state -->
                <div
                  v-if="getProgress(source.name)?.type === 'progress'"
                  class="h-full bg-indigo-500 rounded-full animate-pulse"
                  style="width: 100%;"
                />
              </div>
            </div>
            <!-- Live counts -->
            <div class="flex items-center gap-3 mt-1.5 text-[11px]" style="color: var(--text-3);">
              <span class="text-emerald-600">+{{ getProgress(source.name)?.entries_created ?? 0 }} created</span>
              <span class="text-blue-600">~{{ getProgress(source.name)?.entries_updated ?? 0 }} updated</span>
              <span>{{ getProgress(source.name)?.entries_skipped ?? 0 }} skipped</span>
              <span class="tabular-nums">{{ getProgress(source.name)?.total_processed ?? 0 }} processed</span>
            </div>
          </div>

          <!-- Last run info (shown when no live progress) -->
          <div v-else class="mb-4">
            <template v-if="source.last_run">
              <div class="flex items-center gap-2 text-[11px]">
                <span style="color: var(--text-3);">Last run:</span>
                <span
                  class="font-medium px-1.5 py-0.5 rounded-full border"
                  :class="runStatusBadgeClass(source.last_run.status)"
                >{{ source.last_run.status }}</span>
                <span style="color: var(--text-3);">{{ timeAgo(source.last_run.started_at) }}</span>
              </div>
              <div class="flex items-center gap-3 mt-1.5 text-[11px]" style="color: var(--text-3);">
                <span class="text-emerald-600">+{{ source.last_run.entries_created }} created</span>
                <span class="text-blue-600">~{{ source.last_run.entries_updated }} updated</span>
                <span>{{ source.last_run.entries_skipped }} skipped</span>
              </div>
              <div v-if="source.last_run.errors.length > 0" class="mt-1.5">
                <span class="text-[10px] text-red-500">{{ source.last_run.errors.length }} errors</span>
              </div>
            </template>
            <p v-else class="text-[11px] italic" style="color: var(--text-3);">No runs yet</p>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-2">
            <!-- Cancel button (shown when running) -->
            <button
              v-if="hasLiveProgress(source.name)"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 text-white text-[11px] font-medium hover:bg-red-700 transition-colors"
              :aria-label="`Cancel ingestion for ${sourceDisplayName(source.name)}`"
              @click="handleCancelIngestion(source.name)"
            >
              <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
              Cancel
            </button>
            <!-- Run / Resume buttons (shown when not running) -->
            <template v-else>
              <button
                class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-[11px] font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50"
                :disabled="triggeringSource === source.name"
                :aria-label="`Run ingestion for ${sourceDisplayName(source.name)}`"
                @click="handleTriggerIngestion(source.name)"
              >
                <svg v-if="triggeringSource === source.name" class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                </svg>
                <svg v-else class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {{ triggeringSource === source.name ? 'Starting...' : 'Run Ingestion' }}
              </button>
              <!-- Resume button (shown when last run was cancelled/failed) -->
              <button
                v-if="source.last_run && (source.last_run.status === 'cancelled' || source.last_run.status === 'failed')"
                class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-colors disabled:opacity-50"
                style="color: var(--text-1); border: 1px solid var(--border); background: var(--surface);"
                :disabled="triggeringSource === source.name"
                :aria-label="`Resume ingestion for ${sourceDisplayName(source.name)}`"
                @click="handleResumeIngestion(source.name)"
              >
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Resume
              </button>
            </template>
            <button
              class="px-3 py-1.5 rounded-lg text-[11px] font-medium transition-colors"
              style="color: var(--text-2); border: 1px solid var(--border); background: var(--surface);"
              :aria-label="`View history for ${sourceDisplayName(source.name)}`"
              @click="filterHistory(source.name)"
            >History</button>
          </div>
        </div>
      </div>

      <!-- Ingestion history -->
      <div class="rounded-xl shadow-sm overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
        <div class="px-5 py-3 flex items-center justify-between" style="border-bottom: 1px solid var(--border-light); background: var(--surface-inset);">
          <h2 class="text-[14px] font-semibold" style="color: var(--text-1);">Ingestion History</h2>
          <div class="flex items-center gap-2">
            <select
              v-model="historySourceFilter"
              @change="loadRuns()"
              aria-label="Filter history by source"
              class="rounded-lg px-2.5 py-1 text-[11px] focus:outline-none focus:ring-1"
              style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-2);"
            >
              <option v-for="opt in sourceFilterOptions" :key="opt.key" :value="opt.key">{{ opt.label }}</option>
            </select>
            <span class="text-[11px]" style="color: var(--text-3);">{{ runsTotal }} runs</span>
          </div>
        </div>

        <div v-if="runs.length === 0" class="px-5 py-8 text-center text-[12px] italic" style="color: var(--text-3);">
          No ingestion runs found.
        </div>

        <div v-else class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead style="background: var(--surface-inset); border-bottom: 1px solid var(--border-light);">
              <tr>
                <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Source</th>
                <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Status</th>
                <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Started</th>
                <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Completed</th>
                <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Created</th>
                <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Updated</th>
                <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Skipped</th>
                <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Errors</th>
              </tr>
            </thead>
            <tbody class="divide-y" style="border-color: var(--border-light);">
              <tr
                v-for="run in runs"
                :key="run.id"
                class="hover:bg-indigo-50/40 transition-colors"
              >
                <td class="px-4 py-2.5 font-medium" style="color: var(--text-2);">{{ sourceDisplayName(run.source) }}</td>
                <td class="px-4 py-2.5">
                  <span
                    class="text-[10px] font-medium px-1.5 py-0.5 rounded-full border"
                    :class="runStatusBadgeClass(run.status)"
                  >{{ run.status }}</span>
                </td>
                <td class="px-4 py-2.5" style="color: var(--text-3);">{{ formatDate(run.started_at) }}</td>
                <td class="px-4 py-2.5" style="color: var(--text-3);">{{ formatDate(run.completed_at) }}</td>
                <td class="px-4 py-2.5 text-emerald-600 tabular-nums">{{ run.entries_created }}</td>
                <td class="px-4 py-2.5 text-blue-600 tabular-nums">{{ run.entries_updated }}</td>
                <td class="px-4 py-2.5 tabular-nums" style="color: var(--text-3);">{{ run.entries_skipped }}</td>
                <td class="px-4 py-2.5">
                  <span v-if="run.errors.length > 0" class="text-red-500 font-medium" :title="run.errors.join('\n')">
                    {{ run.errors.length }}
                  </span>
                  <span v-else style="color: var(--text-3);">0</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </template>

  </div>
</template>
