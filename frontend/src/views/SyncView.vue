<!--
  Sync view — full/incremental sync, per-phase sync buttons, live progress, history.
-->
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useSyncStore } from '@/stores/useSyncStore'
import { useWebSocket } from '@/composables/useWebSocket'
import { formatDateTime, formatRelativeTime } from '@/utils/formatters'
import type { SyncProgressMessage } from '@/types/sync'
import * as configApi from '@/api/config'
import * as syncApi from '@/api/sync'

const props = withDefaults(defineProps<{
  /** Source adapter key (e.g. 'sentinelone', 'crowdstrike'). */
  source?: string
  /** Human-readable source label. */
  sourceLabel?: string
  /** Phase keys to display for this source tab. */
  phaseKeys?: string[]
}>(), {
  source: 'sentinelone',
  sourceLabel: 'SentinelOne',
  phaseKeys: () => ['sites', 'groups', 'agents', 'apps', 'tags'],
})

const syncStore = useSyncStore()

const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/v1/sync/progress`
let _lastWsMessageAt = 0
const { connect: connectWs, disconnect: disconnectWs } = useWebSocket(
  wsUrl,
  (data) => {
    _lastWsMessageAt = Date.now()
    syncStore.handleProgressMessage(data as SyncProgressMessage)
  },
)

// ── Fetch limits config ───────────────────────────────────────────────────────
const pageSizeAgents       = ref(500)
const pageSizeApps         = ref(500)
const refreshIntervalMins  = ref(0)   // 0 = disabled (global fallback)
const scheduleSitesMins    = ref(0)
const scheduleGroupsMins   = ref(0)
const scheduleAgentsMins   = ref(0)
const scheduleAppsMins     = ref(0)
const scheduleTagsMins     = ref(0)
const isLoadingLimits = ref(false)
const isSavingLimits  = ref(false)
const limitsStatus    = ref<'idle' | 'saved' | 'error'>('idle')

// Timer IDs for status-reset timeouts (cleaned up on unmount)
let _limitsTimer: ReturnType<typeof setTimeout> | null = null
let _backfillTimer: ReturnType<typeof setTimeout> | null = null
let _renormalizeTimer: ReturnType<typeof setTimeout> | null = null
onUnmounted(() => {
  if (_limitsTimer) clearTimeout(_limitsTimer)
  if (_backfillTimer) clearTimeout(_backfillTimer)
  if (_renormalizeTimer) clearTimeout(_renormalizeTimer)
})

async function loadLimits() {
  isLoadingLimits.value = true
  try {
    const cfg = await configApi.getConfig()
    pageSizeAgents.value      = cfg.page_size_agents      ?? pageSizeAgents.value
    pageSizeApps.value        = cfg.page_size_apps        ?? pageSizeApps.value
    refreshIntervalMins.value = cfg.refresh_interval_minutes ?? refreshIntervalMins.value
    scheduleSitesMins.value   = cfg.schedule_sites_minutes  ?? 0
    scheduleGroupsMins.value  = cfg.schedule_groups_minutes ?? 0
    scheduleAgentsMins.value  = cfg.schedule_agents_minutes ?? 0
    scheduleAppsMins.value    = cfg.schedule_apps_minutes   ?? 0
    scheduleTagsMins.value    = cfg.schedule_tags_minutes   ?? 0
  } catch { /* use defaults */ } finally {
    isLoadingLimits.value = false
  }
}

// ── Next refresh countdown ────────────────────────────────────────────────────
const nowMs = ref(Date.now())
let _tickTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => { _tickTimer = setInterval(() => { nowMs.value = Date.now() }, 10_000) })
onUnmounted(() => { if (_tickTimer) clearInterval(_tickTimer) })

function formatCountdown(nextRunAt: string | null | undefined): string | null {
  if (!nextRunAt) return null
  const remainMs = new Date(nextRunAt).getTime() - nowMs.value
  if (remainMs <= 0) return 'due now'
  const mins = Math.ceil(remainMs / 60_000)
  if (mins < 60) return `in ${mins}m`
  const hrs = Math.floor(mins / 60)
  const rem = mins % 60
  return rem ? `in ${hrs}h ${rem}m` : `in ${hrs}h`
}

/** Soonest next refresh across all phases. */
const nextRefreshLabel = computed(() => {
  const sched = syncStore.schedule
  if (!Object.keys(sched).length) return null
  let soonest: string | null = null
  for (const phase of Object.values(sched)) {
    if (!phase.next_run_at || phase.interval_minutes <= 0) continue
    if (!soonest || phase.next_run_at < soonest) soonest = phase.next_run_at
  }
  return formatCountdown(soonest)
})

/** Per-phase next refresh label. */
function phaseNextRefresh(key: string): string | null {
  const sched = syncStore.schedule[key]
  if (!sched || sched.interval_minutes <= 0) return null
  return formatCountdown(sched.next_run_at)
}

async function saveLimits() {
  isSavingLimits.value = true
  limitsStatus.value = 'idle'
  try {
    await configApi.updateConfig({
      page_size_agents: pageSizeAgents.value,
      page_size_apps:   pageSizeApps.value,
      refresh_interval_minutes: refreshIntervalMins.value,
      schedule_sites_minutes:  scheduleSitesMins.value,
      schedule_groups_minutes: scheduleGroupsMins.value,
      schedule_agents_minutes: scheduleAgentsMins.value,
      schedule_apps_minutes:   scheduleAppsMins.value,
      schedule_tags_minutes:   scheduleTagsMins.value,
    })
    limitsStatus.value = 'saved'
    _limitsTimer = setTimeout(() => { limitsStatus.value = 'idle' }, 3000)
  } catch {
    limitsStatus.value = 'error'
    _limitsTimer = setTimeout(() => { limitsStatus.value = 'idle' }, 5000)
  } finally {
    isSavingLimits.value = false
  }
}

onMounted(async () => {
  await syncStore.fetchStatus()
  await syncStore.fetchHistory()
  loadLimits()
  // Always connect WS — the backend sends current state on connect,
  // so we'll pick up resumed syncs even if fetchStatus returned stale data.
  connectWs()
})

// Note: fetchStatus/fetchHistory are now called directly in
// handleProgressMessage when sync completes/fails, which is more
// reliable than a watcher (Vue batches the status change and null
// assignment in the same tick, so watchers may miss the transition).

// ── Staleness guard ──────────────────────────────────────────────────────────
// If currentRun is "running" but no WS message arrives for 5 minutes,
// the backend may have crashed.  Poll GET /sync/status to detect this.
const STALE_TIMEOUT_MS = 5 * 60_000
let _staleCheckTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  _staleCheckTimer = setInterval(async () => {
    if (
      syncStore.currentRun?.status === 'running' &&
      _lastWsMessageAt > 0 &&
      Date.now() - _lastWsMessageAt > STALE_TIMEOUT_MS
    ) {
      await syncStore.fetchStatus()
    }
  }, 60_000)
})
onUnmounted(() => { if (_staleCheckTimer) clearInterval(_staleCheckTimer); disconnectWs() })

async function trigger(mode: 'full' | 'incremental' | 'auto', phases?: string[]) {
  // Pass the source's phase keys if no explicit phases given
  const targetPhases = phases ?? props.phaseKeys
  const ok = await syncStore.triggerSync(mode, targetPhases)
  if (ok) connectWs()
}

function isPhaseRunning(key: string): boolean {
  return syncStore.phaseDetails[key]?.status === 'running'
}

async function triggerPhase(phase: string) {
  try {
    await syncApi.triggerPhase(phase, 'auto')
    connectWs()
  } catch { /* 409 = already running, ignore */ }
}

async function triggerRefresh() {
  try {
    await syncApi.triggerRefresh()
    connectWs()
  } catch { /* 409 = already running, ignore */ }
}

// ── Cancel ────────────────────────────────────────────────────────────────────
const isCancelling = ref(false)

async function cancelSync() {
  isCancelling.value = true
  try {
    await syncApi.cancelSync()
  } catch { /* 404 = not running, ignore */ } finally {
    isCancelling.value = false
  }
}

// ── Backfill ──────────────────────────────────────────────────────────────────

const isBackfilling = ref(false)
const backfillStatus = ref<'idle' | 'started' | 'error'>('idle')

async function runBackfill() {
  isBackfilling.value = true
  backfillStatus.value = 'idle'
  try {
    await syncApi.backfillAppNames()
    backfillStatus.value = 'started'
    _backfillTimer = setTimeout(() => { backfillStatus.value = 'idle' }, 5000)
  } catch {
    backfillStatus.value = 'error'
    _backfillTimer = setTimeout(() => { backfillStatus.value = 'idle' }, 5000)
  } finally {
    isBackfilling.value = false
  }
}

const isRenormalizing = ref(false)
const renormalizeStatus = ref<'idle' | 'started' | 'error'>('idle')

async function runRenormalize() {
  isRenormalizing.value = true
  renormalizeStatus.value = 'idle'
  try {
    await syncApi.renormalizeApps()
    renormalizeStatus.value = 'started'
    _renormalizeTimer = setTimeout(() => { renormalizeStatus.value = 'idle' }, 5000)
  } catch {
    renormalizeStatus.value = 'error'
    _renormalizeTimer = setTimeout(() => { renormalizeStatus.value = 'idle' }, 5000)
  } finally {
    isRenormalizing.value = false
  }
}

const isSyncing = computed(() =>
  syncStore.currentRun?.status === 'running' ||
  Object.values(syncStore.phaseDetails).some(p => p.status === 'running'),
)

// ── Phase definitions ─────────────────────────────────────────────────────────

/** Phase metadata — keyed by phase name. */
const ALL_PHASE_META: Record<string, { label: string; description: string; syncedKey: string; totalKey: string }> = {
  sites:      { label: 'Sites',        description: 'Sites & account info',      syncedKey: 'sites_synced',  totalKey: 'sites_total' },
  tags:       { label: 'Tags',         description: 'Source tag definitions',     syncedKey: 'tags_synced',   totalKey: 'tags_total' },
  groups:     { label: 'Groups',       description: 'Agent groups per site',      syncedKey: 'groups_synced', totalKey: 'groups_total' },
  agents:     { label: 'Agents',       description: 'Endpoint agents',            syncedKey: 'agents_synced', totalKey: 'agents_total' },
  apps:       { label: 'Applications', description: 'Installed software per agent', syncedKey: 'apps_synced', totalKey: 'apps_total' },
  // CrowdStrike phases (map to same count fields as S1)
  cs_groups:  { label: 'Groups',       description: 'Host groups',               syncedKey: 'groups_synced', totalKey: 'groups_total' },
  cs_agents:  { label: 'Agents',       description: 'Endpoint hosts',            syncedKey: 'agents_synced', totalKey: 'agents_total' },
  cs_apps:    { label: 'Applications', description: 'Falcon Discover apps',      syncedKey: 'apps_synced',   totalKey: 'apps_total' },
}

/** Active phase definitions — filtered by the source's phase keys. */
const PHASE_DEFS = computed(() =>
  props.phaseKeys
    .filter((key) => ALL_PHASE_META[key])
    .map((key) => {
      const meta = ALL_PHASE_META[key]
      return {
        key,
        label: meta.label,
        description: meta.description,
        syncPhases: [key],
        synced: (c: any) => c?.[meta.syncedKey] ?? 0,
        total:  (c: any) => c?.[meta.totalKey] ?? 0,
      }
    })
)

// When not syncing, show actual DB totals so a 272-agent incremental refresh
// doesn't make the fleet look like it only has 272 agents.
const restingCounts = computed(() => {
  const db = syncStore.dbCounts
  if (!db) return null
  return {
    sites_synced: db.sites, sites_total: db.sites,
    groups_synced: db.groups, groups_total: db.groups,
    agents_synced: db.agents, agents_total: db.agents,
    apps_synced: db.apps, apps_total: db.apps,
    tags_synced: db.tags, tags_total: db.tags,
    errors: 0,
  }
})

/** Build display counts: use phase_details (live) for active phases,
 *  DB resting counts for idle phases. */
const activeCounts = computed(() => {
  const rest = restingCounts.value
  const pd = syncStore.phaseDetails
  if (!rest && !Object.keys(pd).length) return null

  const pick = (key: string, syncedKey: string, totalKey: string) => {
    const d = pd[key]
    if (d && d.status !== 'idle') return { synced: d.synced, total: d.total }
    return { synced: (rest as any)?.[syncedKey] ?? 0, total: (rest as any)?.[totalKey] ?? 0 }
  }

  const s = pick('sites', 'sites_synced', 'sites_total')
  const g = pick('groups', 'groups_synced', 'groups_total')
  const a = pick('agents', 'agents_synced', 'agents_total')
  const ap = pick('apps', 'apps_synced', 'apps_total')
  const t = pick('tags', 'tags_synced', 'tags_total')

  return {
    sites_synced: s.synced, sites_total: s.total,
    groups_synced: g.synced, groups_total: g.total,
    agents_synced: a.synced, agents_total: a.total,
    apps_synced: ap.synced, apps_total: ap.total,
    tags_synced: t.synced, tags_total: t.total,
    errors: syncStore.currentRun?.counts?.errors ?? 0,
  }
})

function phaseStatus(key: string): 'done' | 'active' | 'pending' {
  const pd = syncStore.phaseDetails[key]
  if (pd && pd.status !== 'idle') {
    if (pd.status === 'running') return 'active'
    return 'done' // completed, failed, cancelled
  }
  // No live data — show resting state
  return syncStore.lastCompletedRun?.status === 'completed' ? 'done' : 'pending'
}

function pct(synced: number, total: number): number {
  if (!total) return 0
  return Math.min(Math.round((synced / total) * 100), 100)
}

/** Bar width % for a phase — handles done-with-no-totals and active-indeterminate. */
function barPct(key: string, synced: number, total: number): number {
  const status = phaseStatus(key)
  if (status === 'done') return total > 0 ? pct(synced, total) : 100
  if (status === 'active') {
    if (!total) return synced > 0 ? 50 : 15
    return pct(synced, total)
  }
  return pct(synced, total)
}
</script>

<template>
  <div class="p-6 space-y-5 max-w-[860px]">

    <!-- ── Trigger card ───────────────────────────────────────────────────── -->
    <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">

      <!-- Header -->
      <div class="px-6 py-5" style="border-bottom: 1px solid var(--border-light);">
        <h2 class="text-[15px] font-semibold" style="color: var(--heading);">{{ sourceLabel }} Sync</h2>
        <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Pull data from {{ sourceLabel }} into your canonical inventory</p>
      </div>

      <!-- Full / Incremental buttons -->
      <div class="px-6 py-4 flex flex-wrap items-center gap-3" style="border-bottom: 1px solid var(--border-light);">
        <button
          class="flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed bg-[var(--brand-primary)] hover:bg-[var(--brand-primary-dark)] text-white"
          :disabled="isSyncing"
          aria-label="Start full sync"
          @click="trigger('full')"
        >
          <svg class="w-3.5 h-3.5 shrink-0" :class="{ 'animate-spin': isSyncing }" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Full Sync
        </button>
        <button
          class="flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed border border-[var(--success-border)] text-[var(--success-text)] hover:border-[var(--success-text)] hover:text-[var(--success-text)]"
          style="background: var(--surface);"
          :disabled="isSyncing"
          aria-label="Start incremental refresh"
          @click="triggerRefresh()"
          title="Fetch new installs via installedAt filter — no full re-stream of apps"
        >
          <svg class="w-3.5 h-3.5 shrink-0" :class="{ 'animate-spin': isSyncing }" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
        <button
          v-if="isSyncing"
          class="flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed border border-[var(--error-border)] text-[var(--error-text)] hover:border-[var(--error-text)] hover:text-[var(--error-text)]"
          style="background: var(--surface);"
          :disabled="isCancelling"
          aria-label="Cancel running sync"
          @click="cancelSync()"
        >
          <svg class="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
          {{ isCancelling ? 'Cancelling…' : 'Cancel' }}
        </button>
        <p class="text-[11px] ml-auto hidden sm:block" style="color: var(--text-3);">
          Full Sync replaces all data · Refresh fetches only new installs since last run
        </p>
      </div>

      <!-- Per-phase sync buttons -->
      <div class="px-6 py-4" style="border-bottom: 1px solid var(--border-light);">
        <p class="text-[11px] font-semibold uppercase tracking-widest mb-3" style="color: var(--text-3);">Sync individual data type</p>
        <div class="grid grid-cols-2 gap-2" :class="PHASE_DEFS.length >= 5 ? 'sm:grid-cols-5' : 'sm:grid-cols-3'">
          <button
            v-for="phase in PHASE_DEFS"
            :key="phase.key"
            class="flex flex-col items-start px-3 py-2.5 rounded-lg text-left transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            :class="isPhaseRunning(phase.key) ? 'border-[var(--brand-primary-light)] bg-[var(--brand-primary-light)]' : ''"
            :style="isPhaseRunning(phase.key) ? 'border: 1px solid;' : `border: 1px solid var(--border); background: var(--surface-inset);`"
            :disabled="isPhaseRunning(phase.key)"
            :aria-label="`Sync ${phase.label}`"
            @click="triggerPhase(phase.key)"
          >
            <span class="flex items-center gap-1.5 text-[12px] font-semibold" style="color: var(--text-1);">
              <svg v-if="isPhaseRunning(phase.key)" class="w-3 h-3 animate-spin text-[var(--brand-primary)] shrink-0" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              {{ phase.label }}
            </span>
            <span class="text-[10px] mt-0.5 leading-tight" style="color: var(--text-3);">{{ phase.description }}</span>
          </button>
        </div>
      </div>

      <!-- Status row -->
      <div class="px-6 py-3 flex items-center gap-3 min-h-[44px]" style="background: var(--surface-inset);" aria-live="polite">
        <span
          class="w-2 h-2 rounded-full shrink-0"
          :style="
            isSyncing ? 'background: var(--info-text);' :
            syncStore.lastCompletedRun?.status === 'completed'   ? 'background: var(--status-ok-text);' :
            syncStore.lastCompletedRun?.status === 'interrupted' ? 'background: var(--status-warn-text);' :
            syncStore.lastCompletedRun?.status === 'failed'      ? 'background: var(--status-error-text);' :
            'background: var(--text-3);'
          "
          :class="{ 'animate-pulse': isSyncing }"
        />
        <span class="text-[12px] truncate" style="color: var(--text-2);">
          <template v-if="isSyncing">{{ syncStore.currentRun?.message ?? 'Syncing…' }}</template>
          <template v-else-if="syncStore.lastCompletedRun?.status === 'completed'">
            Last sync completed {{ formatRelativeTime(syncStore.lastCompletedRun.completed_at) }}
          </template>
          <template v-else-if="syncStore.lastCompletedRun?.status === 'interrupted'">
            Last sync interrupted — {{ formatRelativeTime(syncStore.lastCompletedRun.completed_at) }}
          </template>
          <template v-else-if="syncStore.lastCompletedRun?.status === 'failed'">
            Last sync failed — {{ formatRelativeTime(syncStore.lastCompletedRun.completed_at) }}
          </template>
          <template v-else>No sync has been run yet</template>
        </span>
        <!-- Next refresh countdown -->
        <span
          v-if="!isSyncing && nextRefreshLabel"
          class="shrink-0 text-[11px] whitespace-nowrap"
          style="color: var(--text-3);"
          title="Next scheduled refresh"
        >Next refresh {{ nextRefreshLabel }}</span>
        <!-- Error count from active run OR last completed run -->
        <span
          v-if="isSyncing && (syncStore.currentRun?.counts.errors ?? 0) > 0"
          class="ml-auto shrink-0 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-[var(--error-bg)] text-[var(--error-text)]"
        >
          {{ syncStore.currentRun!.counts.errors }} error{{ syncStore.currentRun!.counts.errors > 1 ? 's' : '' }}
        </span>
        <span
          v-else-if="!isSyncing && (syncStore.lastCompletedRun?.counts.errors ?? 0) > 0"
          class="ml-auto shrink-0 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-[var(--error-bg)] text-[var(--error-text)]"
        >
          {{ syncStore.lastCompletedRun!.counts.errors }} error{{ syncStore.lastCompletedRun!.counts.errors > 1 ? 's' : '' }}
        </span>
      </div>

      <!-- Progress bars -->
      <div v-if="activeCounts" class="px-6 py-5 space-y-4">
        <div
          v-for="phase in PHASE_DEFS"
          :key="phase.key"
          class="space-y-1.5 transition-opacity"
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2.5">
              <span class="w-4 h-4 flex items-center justify-center shrink-0">
                <svg v-if="phaseStatus(phase.key) === 'active'" class="w-3.5 h-3.5 animate-spin text-[var(--brand-primary)]" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"/>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
                <svg v-else-if="phaseStatus(phase.key) === 'done'" class="w-3.5 h-3.5 text-[var(--success-text)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
                </svg>
                <span v-else class="w-1.5 h-1.5 rounded-full bg-[var(--text-3)] block mx-auto"/>
              </span>
              <span
                class="text-[13px] font-medium"
                :style="{
                  color: phaseStatus(phase.key) === 'active' ? 'var(--text-1)'
                       : phaseStatus(phase.key) === 'done' ? 'var(--text-2)'
                       : 'var(--text-3)',
                }"
              >{{ phase.label }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span
                v-if="!isSyncing && phaseNextRefresh(phase.key)"
                class="text-[10px] whitespace-nowrap"
                style="color: var(--text-3);"
                :title="`Next scheduled refresh for ${phase.label}`"
              >{{ phaseNextRefresh(phase.key) }}</span>
              <span
                class="text-[12px] tabular-nums font-medium"
                :class="{
                  'text-[var(--brand-primary)]': phaseStatus(phase.key) === 'active',
                }"
                :style="phaseStatus(phase.key) === 'done' ? 'color: var(--text-3);' : (phaseStatus(phase.key) === 'pending' ? 'color: var(--text-3); opacity: 0.5;' : '')"
              >
                <template v-if="phase.total(activeCounts) > 0">
                  {{ phase.synced(activeCounts).toLocaleString() }} / {{ phase.total(activeCounts).toLocaleString() }}
                </template>
                <template v-else-if="phaseStatus(phase.key) === 'done'">done</template>
                <template v-else-if="phaseStatus(phase.key) === 'active'">syncing…</template>
                <template v-else>—</template>
              </span>
            </div>
          </div>

          <div
            class="h-[5px] rounded-full overflow-hidden"
            :class="{
              'bg-[var(--brand-primary-light)]':  phaseStatus(phase.key) === 'active',
              'bg-[var(--success-bg)]': phaseStatus(phase.key) === 'done',
              '':   phaseStatus(phase.key) === 'pending',
            }" style="background: var(--surface-hover);"
            role="progressbar"
            :aria-label="`${phase.label} sync progress`"
            :aria-valuenow="barPct(phase.key, phase.synced(activeCounts), phase.total(activeCounts))"
            aria-valuemin="0"
            aria-valuemax="100"
          >
            <div
              class="h-full rounded-full transition-all duration-300 ease-out"
              :class="{
                'bg-[var(--brand-primary)]':  phaseStatus(phase.key) === 'active',
                'bg-[var(--success-text)]': phaseStatus(phase.key) === 'done',
                'bg-[var(--badge-bg)]':   phaseStatus(phase.key) === 'pending',
                'animate-pulse':  phaseStatus(phase.key) === 'active' && !phase.total(activeCounts),
              }"
              :style="{ width: `${barPct(phase.key, phase.synced(activeCounts), phase.total(activeCounts))}%` }"
            />
          </div>
        </div>
      </div>

      <div v-else class="px-6 py-8 text-center text-[13px] italic" style="color: var(--text-3);">
        Trigger a sync to see live progress
      </div>
    </div>

    <!-- ── Data maintenance ────────────────────────────────────────────────── -->
    <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
      <div class="px-6 py-4" style="border-bottom: 1px solid var(--border-light);">
        <h2 class="text-[14px] font-semibold" style="color: var(--heading);">Data Maintenance</h2>
        <p class="text-[12px] mt-0.5" style="color: var(--text-3);">One-time operations for migrating or repairing stored data</p>
      </div>
      <div class="px-6 py-4 flex items-center justify-between gap-4">
        <div class="min-w-0">
          <p class="text-[13px] font-medium" style="color: var(--text-1);">Backfill app names onto agents</p>
          <p class="text-[12px] mt-0.5" style="color: var(--text-3);">
            Reads all installed apps, groups by agent, and writes a compact
            <code class="font-mono text-[11px] px-1 rounded" style="background: var(--surface-inset);">installed_app_names</code>
            array onto each agent document. Run this once after upgrading to enable fast classification.
          </p>
        </div>
        <div class="shrink-0 flex items-center gap-3">
          <span
            v-if="backfillStatus === 'started'"
            class="text-[12px] text-[var(--success-text)] font-medium"
          >Started in background ✓</span>
          <span
            v-else-if="backfillStatus === 'error'"
            class="text-[12px] text-[var(--error-text)] font-medium"
          >Failed — check server logs</span>
          <button
            class="flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            :class="isBackfilling
              ? 'cursor-not-allowed'
              : ''"
            :style="isBackfilling
              ? 'background: var(--badge-bg); color: var(--text-3);'
              : 'background: var(--surface); border: 1px solid var(--border); color: var(--text-2);'"
            :disabled="isBackfilling"
            aria-label="Run app names backfill"
            @click="runBackfill"
          >
            <svg
              class="w-3.5 h-3.5"
              :class="isBackfilling ? 'animate-spin' : ''"
              fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"
            >
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {{ isBackfilling ? 'Starting…' : 'Run Backfill' }}
          </button>
        </div>
      </div>
      <!-- Renormalize app names -->
      <div class="px-6 py-4 flex items-center justify-between gap-4" style="border-top: 1px solid var(--border-light);">
        <div class="min-w-0">
          <p class="text-[13px] font-medium" style="color: var(--text-1);">Re-normalize app names</p>
          <p class="text-[12px] mt-0.5" style="color: var(--text-3);">
            Strips version suffixes (e.g. <code class="font-mono text-[11px] px-1 rounded" style="background: var(--surface-inset);"> - 14.36.32543</code>)
            from all app names in <code class="font-mono text-[11px] px-1 rounded" style="background: var(--surface-inset);">installed_apps</code>,
            then rebuilds <code class="font-mono text-[11px] px-1 rounded" style="background: var(--surface-inset);">installed_app_names</code> on agents.
            Run after upgrading the normalizer so existing data matches the new logic.
          </p>
        </div>
        <div class="shrink-0 flex items-center gap-3">
          <span v-if="renormalizeStatus === 'started'" class="text-[12px] text-[var(--success-text)] font-medium">Started in background ✓</span>
          <span v-else-if="renormalizeStatus === 'error'" class="text-[12px] text-[var(--error-text)] font-medium">Failed — check server logs</span>
          <button
            class="flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            :class="isRenormalizing
              ? 'cursor-not-allowed'
              : ''"
            :style="isRenormalizing
              ? 'background: var(--badge-bg); color: var(--text-3);'
              : 'background: var(--surface); border: 1px solid var(--border); color: var(--text-2);'"
            :disabled="isRenormalizing"
            aria-label="Re-normalize app names"
            @click="runRenormalize"
          >
            <svg
              class="w-3.5 h-3.5"
              :class="isRenormalizing ? 'animate-spin' : ''"
              fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"
            >
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {{ isRenormalizing ? 'Starting…' : 'Re-normalize' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── History ─────────────────────────────────────────────────────────── -->
    <div>
      <h2 class="text-[12px] font-semibold uppercase tracking-widest mb-3" style="color: var(--text-3);">Sync History</h2>

      <div v-if="syncStore.history.length === 0" class="text-[13px] text-center py-10" style="color: var(--text-3);">
        No sync history yet.
      </div>

      <div v-else class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
        <table class="w-full border-collapse">
          <thead>
            <tr style="background: var(--surface-inset); border-bottom: 1px solid var(--border);">
              <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Started</th>
              <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Mode</th>
              <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Status</th>
              <th scope="col" class="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Groups</th>
              <th scope="col" class="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Agents</th>
              <th scope="col" class="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Apps</th>
              <th scope="col" class="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Tags</th>
              <th scope="col" class="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Errors</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="run in syncStore.history"
              :key="run.id"
              class="last:border-0 transition-colors"
              style="border-bottom: 1px solid var(--border-light);"
            >
              <td class="px-4 py-3 text-[12px] tabular-nums" style="color: var(--text-2);">{{ formatDateTime(run.started_at) }}</td>
              <td class="px-4 py-3">
                <span
                  class="text-[11px] font-medium px-1.5 py-0.5 rounded"
                  :class="run.mode === 'full' ? 'bg-[var(--brand-primary-light)] text-[var(--brand-primary)]' : ' text-muted'" style="background: var(--surface-hover);"
                >{{ run.mode }}</span>
              </td>
              <td class="px-4 py-3">
                <span
                  class="text-[11px] font-semibold px-2 py-0.5 rounded-full"
                  :style="
                    run.status === 'running'     ? 'background: var(--info-bg); color: var(--info-text);' :
                    run.status === 'completed'   ? 'background: var(--status-ok-bg); color: var(--status-ok-text);' :
                    run.status === 'interrupted' ? 'background: var(--status-warn-bg); color: var(--status-warn-text);' :
                    run.status === 'failed'      ? 'background: var(--status-error-bg); color: var(--status-error-text);' : ''
                  "
                >{{ run.status }}</span>
              </td>
              <td class="px-4 py-3 text-[12px] tabular-nums text-right" style="color: var(--text-2);">{{ run.counts.groups_synced }}</td>
              <td class="px-4 py-3 text-[12px] tabular-nums text-right" style="color: var(--text-2);">{{ run.counts.agents_synced }}</td>
              <td class="px-4 py-3 text-[12px] tabular-nums text-right" style="color: var(--text-2);">{{ run.counts.apps_synced }}</td>
              <td class="px-4 py-3 text-[12px] tabular-nums text-right" style="color: var(--text-2);">{{ run.counts.tags_synced ?? 0 }}</td>
              <td
                class="px-4 py-3 text-[12px] tabular-nums text-right"
                :class="run.counts.errors > 0 ? 'text-[var(--error-text)] font-semibold' : ''"
                :style="run.counts.errors > 0 ? '' : 'color: var(--text-3); opacity: 0.5;'"
              >{{ run.counts.errors }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ── Settings ──────────────────────────────────────────────────────────── -->
    <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
      <div class="px-6 py-4" style="border-bottom: 1px solid var(--border-light);">
        <h2 class="text-[14px] font-semibold" style="color: var(--heading);">Sync Settings</h2>
        <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Page sizes and per-phase refresh schedules</p>
      </div>
      <div class="px-6 py-5">
        <div v-if="isLoadingLimits" class="text-[12px] italic" style="color: var(--text-3);">Loading…</div>
        <template v-else>
          <!-- Page sizes -->
          <p class="text-[11px] font-semibold uppercase tracking-widest mb-3" style="color: var(--text-3);">API Page Sizes</p>
          <div class="grid grid-cols-2 gap-4 max-w-xs">
            <div class="space-y-1.5">
              <label for="page-size-agents" class="text-[12px] font-medium" style="color: var(--text-2);">Agents</label>
              <input
                id="page-size-agents"
                v-model.number="pageSizeAgents"
                type="number" min="10" max="5000" step="50"
                aria-label="Page size for agents"
                class="w-full px-3 py-2 text-[13px] rounded-lg outline-none transition"
                style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
              />
            </div>
            <div class="space-y-1.5">
              <label for="page-size-apps" class="text-[12px] font-medium" style="color: var(--text-2);">Installed Apps</label>
              <input
                id="page-size-apps"
                v-model.number="pageSizeApps"
                type="number" min="10" max="5000" step="50"
                aria-label="Page size for installed apps"
                class="w-full px-3 py-2 text-[13px] rounded-lg outline-none transition"
                style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
              />
            </div>
          </div>

          <!-- Per-phase schedules -->
          <p class="text-[11px] font-semibold uppercase tracking-widest mt-6 mb-3" style="color: var(--text-3);">Refresh Schedule (minutes, 0 = use default)</p>
          <div class="grid grid-cols-3 sm:grid-cols-6 gap-3">
            <div class="space-y-1.5">
              <label for="sched-default" class="text-[12px] font-medium" style="color: var(--text-2);">Default</label>
              <input
                id="sched-default"
                v-model.number="refreshIntervalMins"
                type="number" min="0" max="10080" step="5"
                aria-label="Default refresh interval"
                class="w-full px-3 py-2 text-[13px] rounded-lg outline-none transition"
                style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
              />
            </div>
            <div class="space-y-1.5">
              <label for="sched-sites" class="text-[12px] font-medium" style="color: var(--text-2);">Sites</label>
              <input
                id="sched-sites"
                v-model.number="scheduleSitesMins"
                type="number" min="0" max="10080" step="5"
                aria-label="Sites refresh interval"
                class="w-full px-3 py-2 text-[13px] rounded-lg outline-none transition"
                style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
              />
            </div>
            <div class="space-y-1.5">
              <label for="sched-groups" class="text-[12px] font-medium" style="color: var(--text-2);">Groups</label>
              <input
                id="sched-groups"
                v-model.number="scheduleGroupsMins"
                type="number" min="0" max="10080" step="5"
                aria-label="Groups refresh interval"
                class="w-full px-3 py-2 text-[13px] rounded-lg outline-none transition"
                style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
              />
            </div>
            <div class="space-y-1.5">
              <label for="sched-agents" class="text-[12px] font-medium" style="color: var(--text-2);">Agents</label>
              <input
                id="sched-agents"
                v-model.number="scheduleAgentsMins"
                type="number" min="0" max="10080" step="5"
                aria-label="Agents refresh interval"
                class="w-full px-3 py-2 text-[13px] rounded-lg outline-none transition"
                style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
              />
            </div>
            <div class="space-y-1.5">
              <label for="sched-apps" class="text-[12px] font-medium" style="color: var(--text-2);">Apps</label>
              <input
                id="sched-apps"
                v-model.number="scheduleAppsMins"
                type="number" min="0" max="10080" step="5"
                aria-label="Apps refresh interval"
                class="w-full px-3 py-2 text-[13px] rounded-lg outline-none transition"
                style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
              />
            </div>
            <div class="space-y-1.5">
              <label for="sched-tags" class="text-[12px] font-medium" style="color: var(--text-2);">Tags</label>
              <input
                id="sched-tags"
                v-model.number="scheduleTagsMins"
                type="number" min="0" max="10080" step="5"
                aria-label="Tags refresh interval"
                class="w-full px-3 py-2 text-[13px] rounded-lg outline-none transition"
                style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
              />
            </div>
          </div>
          <p class="text-[11px] mt-2" style="color: var(--text-3);">
            Each phase syncs independently on its own schedule. Set 0 to use the default interval. Set default to 0 to disable auto-sync.
          </p>

          <div class="flex items-center justify-between mt-4">
            <div class="flex items-center gap-3 ml-auto">
              <span v-if="limitsStatus === 'saved'" class="text-[12px] font-medium text-[var(--success-text)] flex items-center gap-1">
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                Saved
              </span>
              <span v-else-if="limitsStatus === 'error'" class="text-[12px] font-medium text-[var(--error-text)]">Save failed</span>
              <button
                class="px-4 py-1.5 rounded-lg bg-[var(--brand-primary)] hover:bg-[var(--brand-primary-dark)] text-white text-[13px] font-medium transition-colors disabled:opacity-50"
                :disabled="isSavingLimits || isLoadingLimits"
                aria-label="Save settings"
                @click="saveLimits"
              >
                {{ isSavingLimits ? 'Saving…' : 'Save' }}
              </button>
            </div>
          </div>
        </template>
      </div>
    </div>

  </div>
</template>
