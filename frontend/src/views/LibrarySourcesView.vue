<!--
  LibrarySourcesView — admin page for managing fingerprint library ingestion sources.
  Shows source cards with last run status, live progress bar via WebSocket,
  and ingestion history table.
-->
<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import * as libraryApi from '@/api/library'
import * as configApi from '@/api/config'
import * as eolApi from '@/api/eol'
import { useWebSocket } from '@/composables/useWebSocket'
import type { SourceInfo, IngestionRunResponse, IngestionProgressMessage } from '@/types/library'
import type { EOLSourceInfo, EOLSyncProgressMessage } from '@/api/eol'

// ── State ─────────────────────────────────────────────────────────────────────

const sources = ref<SourceInfo[]>([])
const runs = ref<IngestionRunResponse[]>([])
const runsTotal = ref(0)
const isLoading = ref(true)
const error = ref<string | null>(null)
const triggeringSource = ref<string | null>(null)
const triggerError = ref<string | null>(null)

// EOL source state
const eolSource = ref<EOLSourceInfo | null>(null)
const eolSyncing = ref(false)
const eolProgress = ref<EOLSyncProgressMessage | null>(null)

// EOL name mappings
const showMappings = ref(false)
const mappingsBuiltin = ref<{ app_name_prefix: string; eol_product_id: string }[]>([])
const mappingsCustom = ref<{ app_name_prefix: string; eol_product_id: string }[]>([])
const mappingsLoading = ref(false)
const newMappingPrefix = ref('')
const newMappingProduct = ref('')
const mappingSaving = ref(false)

// EOL product dropdown for mapping form
const eolProductOptions = ref<{ id: string; name: string }[]>([])
const productSearchQuery = ref('')
const showProductDropdown = ref(false)

function hideProductDropdownDelayed() {
  globalThis.setTimeout(() => { showProductDropdown.value = false }, 200)
}

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

// ── EOL Sync WebSocket ───────────────────────────────────────────────────────

const eolWsUrl = `${wsProtocol}//${window.location.host}/api/v1/eol/sync/progress`

const { connect: eolWsConnect, disconnect: eolWsDisconnect } = useWebSocket(
  eolWsUrl,
  (data: unknown) => {
    const msg = data as EOLSyncProgressMessage
    if (!msg.source) return

    if (msg.type === 'progress' || msg.status === 'running') {
      eolSyncing.value = true
      eolProgress.value = msg
    }

    if (['completed', 'failed'].includes(msg.type)) {
      eolProgress.value = msg
      loadEolSource()
      setTimeout(() => {
        eolSyncing.value = false
        eolProgress.value = null
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

async function loadEolSource() {
  try {
    eolSource.value = await eolApi.getSourceInfo()
  } catch {
    // Non-critical — EOL source info is optional
  }
}

async function handleEolSync() {
  eolSyncing.value = true
  eolProgress.value = null
  triggerError.value = null
  try {
    await eolApi.triggerSync()
    // Progress updates arrive via WebSocket — no polling needed
  } catch (e) {
    triggerError.value = e instanceof Error ? e.message : 'Failed to trigger EOL sync'
    eolSyncing.value = false
  }
}

async function loadMappings() {
  mappingsLoading.value = true
  try {
    const res = await eolApi.listNameMappings()
    mappingsBuiltin.value = res.builtin
    mappingsCustom.value = res.custom
  } catch {
    // non-critical
  } finally {
    mappingsLoading.value = false
  }
}

async function toggleMappings() {
  showMappings.value = !showMappings.value
  if (showMappings.value && mappingsBuiltin.value.length === 0) {
    await Promise.all([loadMappings(), loadEolProducts()])
  }
}

async function loadEolProducts() {
  try {
    const res = await eolApi.listProducts({ page_size: 200 })
    eolProductOptions.value = res.products.map(p => ({ id: p.product_id, name: p.name }))
  } catch {
    // non-critical
  }
}

const filteredProductOptions = computed(() => {
  const q = productSearchQuery.value.toLowerCase()
  if (!q) return eolProductOptions.value.slice(0, 30)
  return eolProductOptions.value
    .filter(p => p.id.includes(q) || p.name.toLowerCase().includes(q))
    .slice(0, 30)
})

function selectProduct(id: string) {
  newMappingProduct.value = id
  productSearchQuery.value = ''
  showProductDropdown.value = false
}

async function addMapping() {
  if (!newMappingPrefix.value.trim() || !newMappingProduct.value.trim()) return
  mappingSaving.value = true
  try {
    await eolApi.upsertNameMapping({
      app_name_prefix: newMappingPrefix.value.trim().toLowerCase(),
      eol_product_id: newMappingProduct.value.trim(),
    })
    newMappingPrefix.value = ''
    newMappingProduct.value = ''
    await loadMappings()
  } catch {
    // ignore
  } finally {
    mappingSaving.value = false
  }
}

async function deleteMapping(prefix: string) {
  try {
    await eolApi.deleteNameMapping(prefix)
    await loadMappings()
  } catch {
    // ignore
  }
}

function eolStatusBadgeClass(status: string): string {
  switch (status) {
    case 'healthy': return 'bg-[var(--success-bg)] text-[var(--success-text)] border-[var(--success-border)]'
    case 'stale': return 'bg-[var(--warn-bg)] text-[var(--warn-text)] border-[var(--warn-border)]'
    case 'outdated': return 'bg-[var(--error-bg)] text-[var(--error-text)] border-[var(--error-border)]'
    case 'never_synced': return 'bg-[var(--badge-bg)] text-muted border-muted'
    default: return 'bg-[var(--badge-bg)] text-muted border-muted'
  }
}

async function loadAll() {
  isLoading.value = true
  error.value = null
  await Promise.all([loadSources(), loadRuns(), loadNvdKeyStatus(), loadEolSource()])
  isLoading.value = false
}

onMounted(() => {
  loadAll()
  wsConnect()
  eolWsConnect()
})

onUnmounted(() => {
  wsDisconnect()
  eolWsDisconnect()
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
    endoflife: 'endoflife.date',
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
    case 'endoflife': return 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z'
    default: return 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4'
  }
}

function sourceBadgeClass(name: string): string {
  switch (name) {
    case 'nist_cpe': return 'bg-[var(--info-bg)]0/10 text-[var(--info-text)] border-[var(--border)]'
    case 'mitre': return 'bg-purple-500/10 text-purple-600 border-purple-200'
    case 'chocolatey': return 'bg-[var(--warn-bg)]0/10 text-[var(--warn-text)] border-[var(--warn-border)]'
    case 'homebrew': return 'bg-[var(--success-bg)]0/10 text-[var(--success-text)] border-[var(--success-border)]'
    case 'homebrew_cask': return 'bg-[var(--scope-site-bg)]0/10 text-[var(--scope-site-text)] border-[var(--border)]'
    case 'endoflife': return 'bg-orange-500/10 text-orange-600 border-orange-200'
    default: return 'bg-[var(--badge-bg)] text-muted border-muted'
  }
}

function runStatusBadgeClass(status: string): string {
  switch (status) {
    case 'completed': return 'bg-[var(--success-bg)] text-[var(--success-text)] border-[var(--success-border)]'
    case 'running': return 'bg-[var(--info-bg)] text-[var(--info-text)] border-[var(--border)]'
    case 'failed': return 'bg-[var(--error-bg)] text-[var(--error-text)] border-[var(--error-border)]'
    case 'cancelled': return 'bg-[var(--warn-bg)] text-[var(--warn-text)] border-[var(--warn-border)]'
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
            class="text-[12px] hover:text-[var(--info-text)] transition-colors no-underline"
            style="color: var(--text-3);"
            aria-label="Back to library browser"
          >Library</router-link>
          <span class="text-[12px] text-[var(--text-3)]">/</span>
          <span class="text-[12px]" style="color: var(--text-3);">Sources</span>
        </div>
        <h1 class="text-[20px] font-bold" style="color: var(--heading);">Library Sources</h1>
        <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Manage fingerprint library ingestion adapters</p>
      </div>
    </div>

    <!-- NVD API Key -->
    <div class="rounded-xl border px-5 py-4" style="background: var(--surface); border-color: var(--border);">
      <div class="flex items-start gap-3">
        <div class="shrink-0 w-8 h-8 rounded-lg bg-[var(--info-bg)]0/10 flex items-center justify-center mt-0.5">
          <svg class="w-4 h-4 text-[var(--info-text)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <h3 class="text-[14px] font-semibold" style="color: var(--heading);">NVD API Key</h3>
            <span
              v-if="nvdApiKeySet"
              class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-[var(--success-bg)] text-[var(--success-text)] border border-[var(--success-border)]"
            >Configured</span>
            <span
              v-else
              class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-[var(--warn-bg)] text-[var(--warn-text)] border border-[var(--warn-border)]"
            >Not set</span>
          </div>
          <p class="text-[12px] mb-3" style="color: var(--text-3);">
            Speeds up NIST CPE ingestion by 10x. Free at
            <a href="https://nvd.nist.gov/developers/request-an-api-key" target="_blank" rel="noopener" class="text-[var(--info-text)] hover:underline">nvd.nist.gov</a>.
          </p>
          <div class="flex items-center gap-2">
            <template v-if="!nvdApiKeySet">
              <input
                v-model="nvdApiKey"
                type="password"
                placeholder="Paste your NVD API key"
                class="flex-1 max-w-xs px-3 py-1.5 rounded-lg border text-[13px] focus:outline-none focus:ring-2 focus:ring-[var(--input-focus)]/30 focus:border-[var(--brand-primary)]"
                style="background: var(--surface); border-color: var(--border); color: var(--text-1);"
              />
              <button
                :disabled="!nvdApiKey.trim() || nvdSaving"
                class="px-3 py-1.5 rounded-lg bg-[var(--brand-primary)] text-white text-[12px] font-medium hover:opacity-90 transition-colors disabled:opacity-40"
                @click="saveNvdApiKey"
              >{{ nvdSaving ? 'Saving…' : 'Save' }}</button>
            </template>
            <template v-else>
              <span class="text-[12px]" style="color: var(--text-3);">API key is stored securely.</span>
              <button
                :disabled="nvdSaving"
                class="px-3 py-1.5 rounded-lg text-[12px] font-medium border transition-colors hover:border-red-400 hover:text-[var(--error-text)]"
                style="border-color: var(--border); color: var(--text-3);"
                @click="clearNvdApiKey"
              >Remove</button>
            </template>
            <span v-if="nvdSaveStatus === 'saved'" class="text-[11px] text-[var(--success-text)]">Saved</span>
            <span v-if="nvdSaveStatus === 'error'" class="text-[11px] text-[var(--error-text)]">Failed to save</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="flex items-center gap-2 text-[13px] py-10 justify-center" style="color: var(--text-3);">
      <svg class="w-4 h-4 animate-spin text-[var(--brand-primary)]" fill="none" viewBox="0 0 24 24" aria-hidden="true">
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
              <svg class="w-3.5 h-3.5 animate-spin text-[var(--brand-primary)]" fill="none" viewBox="0 0 24 24" aria-hidden="true">
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
                :class="getProgress(source.name)?.type === 'failed' ? 'bg-[var(--error-bg)]0' : getProgress(source.name)?.type === 'completed' ? 'bg-[var(--success-bg)]0' : 'bg-[var(--info-bg)]0'"
                :style="{ width: getProgress(source.name)?.type === 'completed' ? '100%' : 'auto', minWidth: '8px' }"
              >
                <!-- Indeterminate animation for running state -->
                <div
                  v-if="getProgress(source.name)?.type === 'progress'"
                  class="h-full bg-[var(--info-bg)]0 rounded-full animate-pulse"
                  style="width: 100%;"
                />
              </div>
            </div>
            <!-- Live counts -->
            <div class="flex items-center gap-3 mt-1.5 text-[11px]" style="color: var(--text-3);">
              <span class="text-[var(--success-text)]">+{{ getProgress(source.name)?.entries_created ?? 0 }} created</span>
              <span class="text-[var(--info-text)]">~{{ getProgress(source.name)?.entries_updated ?? 0 }} updated</span>
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
                <span class="text-[var(--success-text)]">+{{ source.last_run.entries_created }} created</span>
                <span class="text-[var(--info-text)]">~{{ source.last_run.entries_updated }} updated</span>
                <span>{{ source.last_run.entries_skipped }} skipped</span>
              </div>
              <div v-if="source.last_run.errors.length > 0" class="mt-1.5">
                <span class="text-[10px] text-[var(--error-text)]">{{ source.last_run.errors.length }} errors</span>
              </div>
            </template>
            <p v-else class="text-[11px] italic" style="color: var(--text-3);">No runs yet</p>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-2">
            <!-- Cancel button (shown when running) -->
            <button
              v-if="hasLiveProgress(source.name)"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--error-text)] text-white text-[11px] font-medium hover:opacity-90 transition-colors"
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
                class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--brand-primary)] text-white text-[11px] font-medium hover:opacity-90 transition-colors disabled:opacity-50"
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

      <!-- EOL Lifecycle Data source card -->
      <div
        v-if="eolSource"
        class="rounded-xl shadow-sm p-5"
        style="background: var(--surface); border: 1px solid var(--border);"
      >
        <div class="flex items-start gap-3 mb-3">
          <div class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border bg-orange-500/10 text-orange-600 border-orange-200">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <h3 class="text-[14px] font-semibold" style="color: var(--text-1);">endoflife.date</h3>
              <span
                class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border"
                :class="eolStatusBadgeClass(eolSource.status)"
              >{{ eolSource.status }}</span>
            </div>
            <p class="text-[12px] mt-0.5 leading-relaxed" style="color: var(--text-3);">
              Software lifecycle and End-of-Life tracking data from endoflife.date
            </p>
          </div>
        </div>

        <!-- Live progress bar (shown during sync) -->
        <div v-if="eolProgress && eolSyncing" class="mb-4">
          <div class="flex items-center gap-2 text-[11px] mb-1.5">
            <svg class="w-3.5 h-3.5 animate-spin text-[var(--brand-primary)]" fill="none" viewBox="0 0 24 24" aria-hidden="true">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
            </svg>
            <span class="font-medium" style="color: var(--text-2);">
              {{ eolProgress.message || 'Syncing...' }}
            </span>
          </div>
          <!-- Progress bar -->
          <div class="w-full h-1.5 rounded-full overflow-hidden" style="background: var(--border-light);">
            <div
              class="h-full rounded-full transition-all duration-500 ease-out"
              :class="eolProgress.type === 'failed' ? 'bg-[var(--error-text)]' : eolProgress.type === 'completed' ? 'bg-[var(--success-text)]' : 'bg-[var(--brand-primary)]'"
              :style="{ width: eolProgress.products_total > 0 ? `${Math.round((eolProgress.products_synced + eolProgress.products_failed) / eolProgress.products_total * 100)}%` : '0%' }"
            />
          </div>
          <!-- Live counts -->
          <div class="flex items-center gap-3 mt-1.5 text-[11px]" style="color: var(--text-3);">
            <span class="text-[var(--success-text)]">{{ eolProgress.products_synced }} synced</span>
            <span v-if="eolProgress.products_failed > 0" class="text-[var(--error-text)]">{{ eolProgress.products_failed }} failed</span>
            <span class="tabular-nums">{{ eolProgress.products_synced + eolProgress.products_failed }}/{{ eolProgress.products_total }} products</span>
            <span v-if="eolProgress.apps_matched" class="text-[var(--info-text)]">{{ eolProgress.apps_matched }} apps matched</span>
          </div>
        </div>

        <!-- Completed flash message -->
        <div v-else-if="eolProgress && eolProgress.type === 'completed'" class="mb-4">
          <div class="flex items-center gap-2 text-[11px]">
            <svg class="w-3.5 h-3.5 text-[var(--success-text)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            <span class="font-medium text-[var(--success-text)]">{{ eolProgress.message }}</span>
          </div>
        </div>

        <!-- Stats (shown when not syncing) -->
        <div v-else class="mb-4">
          <div class="flex items-center gap-3 text-[11px]" style="color: var(--text-3);">
            <span class="font-medium" style="color: var(--text-2);">{{ eolSource.total_products }} products tracked</span>
            <span>{{ eolSource.total_eol_cycles }} EOL cycles</span>
            <span class="text-[var(--info-text)]">{{ eolSource.matched_apps }} apps matched</span>
          </div>
          <div v-if="eolSource.last_synced" class="flex items-center gap-2 mt-1.5 text-[11px]" style="color: var(--text-3);">
            <span>Last synced: {{ timeAgo(eolSource.last_synced) }}</span>
          </div>
          <p v-else class="text-[11px] italic mt-1.5" style="color: var(--text-3);">Never synced</p>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-2">
          <button
            class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--brand-primary)] text-white text-[11px] font-medium hover:opacity-90 transition-colors disabled:opacity-50"
            :disabled="eolSyncing"
            aria-label="Sync EOL data from endoflife.date"
            @click="handleEolSync"
          >
            <svg v-if="eolSyncing" class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24" aria-hidden="true">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
            </svg>
            <svg v-else class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {{ eolSyncing ? 'Syncing...' : 'Sync Now' }}
          </button>
          <button
            class="px-3 py-1.5 rounded-lg text-[11px] font-medium transition-colors"
            style="color: var(--text-2); border: 1px solid var(--border); background: var(--surface);"
            @click="toggleMappings"
          >{{ showMappings ? 'Hide Mappings' : 'Name Mappings' }}</button>
        </div>

        <!-- Name mappings panel -->
        <div v-if="showMappings" class="mt-4 pt-4" style="border-top: 1px solid var(--border-light);">
          <h4 class="text-[12px] font-semibold mb-2" style="color: var(--heading);">App Name → EOL Product Mappings</h4>
          <p class="text-[11px] mb-3" style="color: var(--text-3);">
            Maps normalized app names (prefix match) to endoflife.date product slugs.
            Custom mappings override built-in ones. Changes apply on next app sync.
          </p>

          <!-- Add new mapping -->
          <div class="flex items-center gap-2 mb-3">
            <input
              v-model="newMappingPrefix"
              type="text"
              placeholder="App name prefix (e.g. zscaler)"
              class="flex-1 px-2.5 py-1.5 rounded-lg border text-[12px] focus:outline-none focus:ring-1 focus:ring-[var(--input-focus)]"
              style="background: var(--input-bg); border-color: var(--input-border); color: var(--text-1);"
            />
            <div class="flex-1 relative">
              <input
                v-model="productSearchQuery"
                type="text"
                :placeholder="newMappingProduct || 'Search EOL product...'"
                class="w-full px-2.5 py-1.5 rounded-lg border text-[12px] focus:outline-none focus:ring-1 focus:ring-[var(--input-focus)]"
                style="background: var(--input-bg); border-color: var(--input-border); color: var(--text-1);"
                @focus="showProductDropdown = true"
                @blur="hideProductDropdownDelayed"
              />
              <span
                v-if="newMappingProduct && !productSearchQuery"
                class="absolute left-2.5 top-1/2 -translate-y-1/2 text-[12px] font-medium pointer-events-none"
                style="color: var(--text-1);"
              >{{ newMappingProduct }}</span>
              <!-- Dropdown -->
              <div
                v-if="showProductDropdown && filteredProductOptions.length > 0"
                class="absolute z-20 left-0 right-0 mt-1 max-h-48 overflow-y-auto rounded-lg shadow-lg"
                style="background: var(--surface); border: 1px solid var(--border);"
              >
                <button
                  v-for="opt in filteredProductOptions"
                  :key="opt.id"
                  type="button"
                  class="w-full text-left px-3 py-1.5 text-[11px] hover:bg-[var(--surface-hover)] transition-colors flex items-center justify-between"
                  @mousedown.prevent="selectProduct(opt.id)"
                >
                  <span class="font-mono" style="color: var(--text-1);">{{ opt.id }}</span>
                  <span class="text-[10px] ml-2 truncate" style="color: var(--text-3);">{{ opt.name }}</span>
                </button>
              </div>
            </div>
            <button
              :disabled="!newMappingPrefix.trim() || !newMappingProduct.trim() || mappingSaving"
              class="px-3 py-1.5 rounded-lg bg-[var(--brand-primary)] text-white text-[11px] font-medium hover:opacity-90 transition-colors disabled:opacity-40"
              @click="addMapping"
            >{{ mappingSaving ? 'Saving...' : 'Add' }}</button>
          </div>

          <div v-if="mappingsLoading" class="text-[11px] py-4 text-center" style="color: var(--text-3);">Loading mappings...</div>

          <!-- Custom mappings (editable) -->
          <div v-if="mappingsCustom.length > 0" class="mb-3">
            <h5 class="text-[11px] font-semibold mb-1.5" style="color: var(--text-2);">Custom ({{ mappingsCustom.length }})</h5>
            <div class="space-y-1">
              <div
                v-for="m in mappingsCustom"
                :key="m.app_name_prefix"
                class="flex items-center justify-between px-3 py-1.5 rounded-lg text-[11px]"
                style="background: var(--surface-alt); border: 1px solid var(--border-light);"
              >
                <div>
                  <span class="font-mono font-medium" style="color: var(--text-1);">{{ m.app_name_prefix }}</span>
                  <span style="color: var(--text-3);"> → </span>
                  <span class="text-[var(--info-text)]">{{ m.eol_product_id }}</span>
                </div>
                <button
                  class="text-[10px] text-[var(--error-text)] hover:underline"
                  @click="deleteMapping(m.app_name_prefix)"
                >Remove</button>
              </div>
            </div>
          </div>

          <!-- Built-in mappings (read-only) -->
          <details class="text-[11px]">
            <summary class="cursor-pointer font-semibold py-1" style="color: var(--text-2);">
              Built-in ({{ mappingsBuiltin.length }})
            </summary>
            <div class="mt-1 max-h-48 overflow-y-auto space-y-0.5">
              <div
                v-for="m in mappingsBuiltin"
                :key="m.app_name_prefix"
                class="flex items-center px-3 py-1 rounded text-[11px]"
                style="color: var(--text-3);"
              >
                <span class="font-mono" style="color: var(--text-2);">{{ m.app_name_prefix }}</span>
                <span class="mx-1.5"> → </span>
                <span>{{ m.eol_product_id }}</span>
              </div>
            </div>
          </details>
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
                class="hover:bg-[var(--info-bg)]/40 transition-colors"
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
                <td class="px-4 py-2.5 text-[var(--success-text)] tabular-nums">{{ run.entries_created }}</td>
                <td class="px-4 py-2.5 text-[var(--info-text)] tabular-nums">{{ run.entries_updated }}</td>
                <td class="px-4 py-2.5 tabular-nums" style="color: var(--text-3);">{{ run.entries_skipped }}</td>
                <td class="px-4 py-2.5">
                  <span v-if="run.errors.length > 0" class="text-[var(--error-text)] font-medium" :title="run.errors.join('\n')">
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
