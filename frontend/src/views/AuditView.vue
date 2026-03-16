<!--
  Audit Log view — paginated, filterable table of all system/user events.
-->
<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { getAuditLog, type AuditEntry } from '@/api/audit'
import { getChainStatus, type ChainStatusResponse } from '@/api/auditChain'
import { getConfig, updateConfig } from '@/api/config'
import { formatDateTime, formatRelativeTime } from '@/utils/formatters'

const router = useRouter()

// ── State ─────────────────────────────────────────────────────────────────────

const entries    = ref<AuditEntry[]>([])
const total      = ref(0)
const loading    = ref(false)
const error      = ref<string | null>(null)

// Filters
const filterDomain = ref('')
const filterActor  = ref('')
const filterStatus = ref('')
const filterAction = ref('')

// Pagination — default pulled from persisted config
const page  = ref(1)
const limit = ref(100)

// Page size editor
const editingPageSize   = ref(false)
const pendingPageSize   = ref(100)
const savingPageSize    = ref(false)

const totalPages = computed(() => Math.ceil(total.value / limit.value) || 1)

// Chain status
const chainInfo = ref<ChainStatusResponse | null>(null)

// Live indicator
type LiveStatus = 'connecting' | 'live' | 'disconnected'
const liveStatus   = ref<LiveStatus>('disconnected')
const pendingCount = ref(0)   // new events buffered when not on page 1 or filters active

// ── Data loading ──────────────────────────────────────────────────────────────

async function load() {
  loading.value = true
  error.value = null
  pendingCount.value = 0
  try {
    const res = await getAuditLog({
      page:   page.value,
      limit:  limit.value,
      domain: filterDomain.value || undefined,
      actor:  filterActor.value  || undefined,
      status: filterStatus.value || undefined,
      action: filterAction.value || undefined,
    })
    entries.value = res.entries
    total.value   = res.total
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load audit log'
  } finally {
    loading.value = false
  }
}

// Reset to page 1 when filters change
watch([filterDomain, filterActor, filterStatus, filterAction], () => {
  page.value = 1
  load()
})

watch(page, load)

onMounted(async () => {
  try {
    const cfg = await getConfig()
    if (cfg.page_size_audit) {
      limit.value = cfg.page_size_audit
      pendingPageSize.value = cfg.page_size_audit
    }
  } catch { /* use default */ }
  try {
    chainInfo.value = await getChainStatus()
  } catch { /* chain not initialized */ }
  load()
  connectWs()
})

onUnmounted(disconnectWs)

async function savePageSize() {
  savingPageSize.value = true
  try {
    await updateConfig({ page_size_audit: pendingPageSize.value })
    limit.value = pendingPageSize.value
    editingPageSize.value = false
    page.value = 1
    load()
  } catch { /* ignore */ } finally {
    savingPageSize.value = false
  }
}

// ── WebSocket live tail ────────────────────────────────────────────────────────

let ws: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let reconnectAttempts = 0

const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/v1/audit/ws`

function connectWs() {
  if (ws?.readyState === WebSocket.OPEN) return
  liveStatus.value = 'connecting'
  const token = localStorage.getItem('sentora_token')
  const protocols = token ? [`bearer.${token}`] : undefined
  ws = new WebSocket(wsUrl, protocols)

  ws.onopen = () => {
    liveStatus.value = 'live'
    reconnectAttempts = 0
  }

  ws.onmessage = (event) => {
    try {
      const entry = JSON.parse(event.data as string) as AuditEntry
      const onFirstPage = page.value === 1
      const hasFilters  = !!(filterDomain.value || filterActor.value || filterStatus.value || filterAction.value)

      if (onFirstPage && !hasFilters) {
        // Prepend directly and keep the list trimmed to the page limit
        entries.value = [entry, ...entries.value].slice(0, limit.value)
        total.value += 1
      } else {
        pendingCount.value += 1
      }
    } catch { /* ignore malformed frames */ }
  }

  ws.onclose = () => {
    liveStatus.value = 'disconnected'
    const delay = Math.min(1000 * 2 ** reconnectAttempts, 30_000)
    reconnectAttempts++
    reconnectTimer = setTimeout(connectWs, delay)
  }

  ws.onerror = () => {
    ws?.close()
  }
}

function disconnectWs() {
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
  ws?.close()
  ws = null
  liveStatus.value = 'disconnected'
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const DOMAIN_COLORS: Record<string, string> = {
  sync:           'bg-blue-100 text-blue-700',
  config:         'bg-violet-100 text-violet-700',
  fingerprint:    'bg-amber-100 text-amber-700',
  classification: 'bg-indigo-100 text-indigo-700',
  taxonomy:       'bg-teal-100 text-teal-700',
}

const STATUS_COLORS: Record<string, string> = {
  success: 'bg-emerald-100 text-emerald-700',
  failure: 'bg-red-100 text-red-700',
  info:    'badge-neutral',
}

function domainClass(domain: string) {
  return DOMAIN_COLORS[domain] ?? 'badge-neutral'
}

function statusClass(status: string) {
  return STATUS_COLORS[status] ?? 'badge-neutral'
}

// Expand/collapse row details
const expandedIdx = ref<number | null>(null)
function toggleExpand(idx: number) {
  expandedIdx.value = expandedIdx.value === idx ? null : idx
}

function hasDetails(entry: AuditEntry) {
  return Object.keys(entry.details ?? {}).length > 0
}

function detailsJson(entry: AuditEntry) {
  return JSON.stringify(entry.details, null, 2)
}
</script>

<template>
  <div class="p-6 space-y-4 max-w-[1100px]">

    <!-- Header row -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2.5">
        <div>
          <h2 class="text-[15px] font-semibold" style="color: var(--heading);">Audit Log</h2>
          <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Every system and user action, newest first</p>
        </div>
        <!-- Live status dot -->
        <span
          class="w-2 h-2 rounded-full shrink-0 mt-0.5"
          :class="{
            'bg-emerald-400 animate-pulse': liveStatus === 'live',
            'bg-amber-400 animate-pulse':   liveStatus === 'connecting',
            'bg-slate-300':                  liveStatus === 'disconnected',
          }"
          :title="liveStatus === 'live' ? 'Live — new events appear automatically' : liveStatus === 'connecting' ? 'Connecting…' : 'Disconnected'"
        />
      </div>
      <button
        aria-label="Refresh audit log"
        class="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium rounded-md transition-colors"
        style="color: var(--text-2); background: var(--badge-bg);"
        :disabled="loading"
        @click="load"
      >
        <svg class="w-3.5 h-3.5" :class="loading ? 'animate-spin' : ''" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Refresh
      </button>
    </div>

    <!-- Chain status banner -->
    <div
      v-if="chainInfo"
      class="rounded-lg px-4 py-2.5 flex items-center justify-between cursor-pointer transition-colors"
      :style="{
        background: chainInfo.chain_valid === true ? 'var(--status-ok-bg)' : chainInfo.chain_valid === false ? 'var(--status-error-bg)' : 'var(--info-bg)',
        border: `1px solid ${chainInfo.chain_valid === true ? 'var(--success-border)' : chainInfo.chain_valid === false ? 'var(--error-border)' : 'var(--border)'}`,
      }"
      @click="router.push('/audit/chain')"
    >
      <div class="flex items-center gap-2">
        <div
          class="w-2 h-2 rounded-full shrink-0"
          :style="{
            background: chainInfo.chain_valid === true ? 'var(--status-ok-text)' : chainInfo.chain_valid === false ? 'var(--status-error-text)' : 'var(--status-warn-text)',
          }"
        />
        <span class="text-[12px] font-medium" style="color: var(--heading);">
          Audit Chain:
          <span :style="{ color: chainInfo.chain_valid === true ? 'var(--status-ok-text)' : chainInfo.chain_valid === false ? 'var(--status-error-text)' : 'var(--status-warn-text)' }">
            {{ chainInfo.chain_valid === true ? 'Valid' : chainInfo.chain_valid === false ? 'Broken' : 'Not Verified' }}
          </span>
        </span>
        <span class="text-[11px] tabular-nums" style="color: var(--text-3);">
          {{ chainInfo.total_entries.toLocaleString() }} entries, epoch {{ chainInfo.current_epoch }}
        </span>
      </div>
      <span class="text-[11px]" style="color: var(--text-3);">
        View Chain Details &rarr;
      </span>
    </div>

    <!-- Filter bar -->
    <div class="flex flex-wrap items-center gap-2">
      <!-- Domain -->
      <select
        v-model="filterDomain"
        aria-label="Filter by domain"
        class="h-8 px-2.5 text-[12px] rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-300"
        style="background: var(--surface); border: 1px solid var(--input-border); color: var(--text-2);"
      >
        <option value="">All domains</option>
        <option value="sync">Sync</option>
        <option value="config">Config</option>
        <option value="fingerprint">Fingerprint</option>
        <option value="classification">Classification</option>
        <option value="taxonomy">Taxonomy</option>
      </select>

      <!-- Actor -->
      <select
        v-model="filterActor"
        aria-label="Filter by actor"
        class="h-8 px-2.5 text-[12px] rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-300"
        style="background: var(--surface); border: 1px solid var(--input-border); color: var(--text-2);"
      >
        <option value="">All actors</option>
        <option value="user">User</option>
        <option value="system">System</option>
        <option value="scheduler">Scheduler</option>
      </select>

      <!-- Status -->
      <select
        v-model="filterStatus"
        aria-label="Filter by status"
        class="h-8 px-2.5 text-[12px] rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-300"
        style="background: var(--surface); border: 1px solid var(--input-border); color: var(--text-2);"
      >
        <option value="">All statuses</option>
        <option value="success">Success</option>
        <option value="failure">Failure</option>
        <option value="info">Info</option>
      </select>

      <!-- Action text search -->
      <input
        v-model="filterAction"
        type="text"
        placeholder="Filter by action…"
        aria-label="Filter by action"
        class="h-8 px-3 text-[12px] rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-300 w-44"
        style="background: var(--surface); border: 1px solid var(--input-border); color: var(--text-2);"
      />

      <!-- Clear filters -->
      <button
        v-if="filterDomain || filterActor || filterStatus || filterAction"
        aria-label="Clear all filters"
        class="h-8 px-3 text-[12px] rounded-md transition-colors"
        style="color: var(--text-3); border: 1px solid var(--border); background: var(--surface);"
        @click="filterDomain = ''; filterActor = ''; filterStatus = ''; filterAction = ''"
      >Clear</button>

      <!-- Result count + page size editor -->
      <div class="ml-auto flex items-center gap-2">
        <span class="text-[12px] tabular-nums" style="color: var(--text-3);">
          {{ total.toLocaleString() }} event{{ total !== 1 ? 's' : '' }}
        </span>

        <!-- Inline page size editor -->
        <template v-if="editingPageSize">
          <input
            v-model.number="pendingPageSize"
            type="number" min="10" max="1000" step="10"
            aria-label="Page size"
            class="w-20 h-7 px-2 text-[12px] border border-indigo-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-300"
            @keydown.enter="savePageSize"
            @keydown.escape="editingPageSize = false"
          />
          <button
            class="h-7 px-2.5 text-[12px] font-medium bg-indigo-600 hover:bg-indigo-700 text-white rounded-md disabled:opacity-50 transition-colors"
            :disabled="savingPageSize"
            @click="savePageSize"
          >{{ savingPageSize ? '…' : 'Save' }}</button>
          <button
            class="h-7 px-2 text-[12px]"
            style="color: var(--text-3);"
            @click="editingPageSize = false"
          >Cancel</button>
        </template>
        <button
          v-else
          class="h-7 px-2.5 text-[12px] rounded-md transition-colors tabular-nums"
          style="color: var(--text-3); border: 1px solid var(--border); background: var(--surface);"
          :title="`Page size: ${limit}. Click to change.`"
          @click="pendingPageSize = limit; editingPageSize = true"
        >{{ limit }} / page</button>
      </div>
    </div>

    <!-- New events banner (shown when buffering because of filters / non-first page) -->
    <button
      v-if="pendingCount > 0"
      aria-live="polite"
      class="w-full flex items-center justify-center gap-2 py-2 text-[12px] font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100 transition-colors"
      @click="page = 1; filterDomain = ''; filterActor = ''; filterStatus = ''; filterAction = ''; load()"
    >
      <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M5 10l7-7m0 0l7 7m-7-7v18"/>
      </svg>
      {{ pendingCount }} new event{{ pendingCount !== 1 ? 's' : '' }} — click to refresh
    </button>

    <!-- Error -->
    <div v-if="error" class="rounded-lg px-4 py-3 text-[13px]" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);">
      {{ error }}
    </div>

    <!-- Table -->
    <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">

      <!-- Loading overlay -->
      <div v-if="loading && entries.length === 0" class="py-16 text-center text-[13px]" style="color: var(--text-3);">
        Loading…
      </div>

      <!-- Empty state -->
      <div v-else-if="!loading && entries.length === 0" class="py-16 text-center text-[13px] italic" style="color: var(--text-3);">
        No audit events match the current filters.
      </div>

      <table v-else class="w-full border-collapse">
        <thead>
          <tr style="background: var(--surface-inset); border-bottom: 1px solid var(--border);">
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest w-[160px]" style="color: var(--text-3);">Timestamp</th>
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest w-[90px]" style="color: var(--text-3);">Domain</th>
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest w-[70px]" style="color: var(--text-3);">Actor</th>
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest w-[70px]" style="color: var(--text-3);">Status</th>
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Summary</th>
            <th scope="col" class="px-4 py-3 w-8"/>
          </tr>
        </thead>
        <tbody>
          <template v-for="(entry, idx) in entries" :key="idx">
            <!-- Main row -->
            <tr
              class="last:border-0 transition-colors"
              :class="hasDetails(entry) ? 'cursor-pointer' : ''"
              style="border-bottom: 1px solid var(--border-light);"
              :aria-expanded="hasDetails(entry) ? expandedIdx === idx : undefined"
              @click="hasDetails(entry) && toggleExpand(idx)"
            >
              <td class="px-4 py-3 text-[12px] tabular-nums whitespace-nowrap" style="color: var(--text-3);">
                <span :title="formatDateTime(entry.timestamp)">{{ formatRelativeTime(entry.timestamp) }}</span>
              </td>
              <td class="px-4 py-3">
                <span class="text-[11px] font-medium px-2 py-0.5 rounded-full capitalize" :class="domainClass(entry.domain)">
                  {{ entry.domain }}
                </span>
              </td>
              <td class="px-4 py-3 text-[12px] capitalize" style="color: var(--text-2);">{{ entry.actor }}</td>
              <td class="px-4 py-3">
                <span class="text-[11px] font-medium px-2 py-0.5 rounded-full capitalize" :class="statusClass(entry.status)">
                  {{ entry.status }}
                </span>
              </td>
              <td class="px-4 py-3 text-[12px] leading-snug" style="color: var(--text-2);">
                <span class="text-[10px] font-mono mr-2" style="color: var(--text-3);">{{ entry.action }}</span>
                {{ entry.summary }}
              </td>
              <!-- Expand chevron -->
              <td class="px-3 py-3 text-right">
                <svg
                  v-if="hasDetails(entry)"
                  :aria-label="expandedIdx === idx ? 'Collapse details' : 'Expand details'"
                  role="img"
                  class="w-3.5 h-3.5 ml-auto transition-transform"
                  :class="expandedIdx === idx ? 'rotate-180' : ''"
                  style="color: var(--text-3);"
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
                </svg>
              </td>
            </tr>

            <!-- Expanded details row -->
            <tr v-if="expandedIdx === idx && hasDetails(entry)" style="border-bottom: 1px solid var(--border-light); background: var(--surface-inset);">
              <td colspan="6" class="px-4 py-3 pl-16">
                <pre class="text-[11px] font-mono whitespace-pre-wrap break-all leading-relaxed" style="color: var(--text-2);">{{ detailsJson(entry) }}</pre>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="flex items-center justify-between">
      <span class="text-[12px]" style="color: var(--text-3);">
        Page {{ page }} of {{ totalPages }}
      </span>
      <div class="flex items-center gap-1">
        <button
          aria-label="Previous page"
          class="px-3 py-1.5 text-[12px] font-medium rounded-md disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          style="border: 1px solid var(--border); background: var(--surface); color: var(--text-2);"
          :disabled="page <= 1"
          @click="page--"
        >← Prev</button>
        <button
          aria-label="Next page"
          class="px-3 py-1.5 text-[12px] font-medium rounded-md disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          style="border: 1px solid var(--border); background: var(--surface); color: var(--text-2);"
          :disabled="page >= totalPages"
          @click="page++"
        >Next →</button>
      </div>
    </div>

  </div>
</template>
