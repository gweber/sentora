<!--
  Dashboard — fleet health, app intelligence, fingerprinting progress.
-->
<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSyncStore } from '@/stores/useSyncStore'
import { useClassificationStore } from '@/stores/useClassificationStore'
import { useComplianceStore } from '@/stores/useComplianceStore'
import { useEnforcementStore } from '@/stores/useEnforcementStore'
import { formatRelativeTime } from '@/utils/formatters'
import * as dashboardApi from '@/api/dashboard'
import type { FleetStats, AppStats, FingerprintingStats } from '@/api/dashboard'

const router = useRouter()
const syncStore = useSyncStore()
const classStore = useClassificationStore()
const complianceStore = useComplianceStore()
const enforcementStore = useEnforcementStore()

const complianceScore = computed(() => complianceStore.dashboard?.overall_score_percent ?? null)
const complianceViolations = computed(() => complianceStore.dashboard?.total_violations ?? 0)
const enforcementPassing = computed(() => enforcementStore.summary?.passing ?? 0)
const enforcementFailing = computed(() => enforcementStore.summary?.failing ?? 0)
const enforcementViolations = computed(() => enforcementStore.summary?.total_violations ?? 0)

const fleet = ref<FleetStats | null>(null)
const apps = ref<AppStats | null>(null)
const fingerprinting = ref<FingerprintingStats | null>(null)
const loadErrors = ref<string[]>([])

onMounted(() => {
  // Fire all requests independently — each section renders as its data arrives.
  // .catch() prevents unhandled promise rejections.
  syncStore.fetchStatus().catch(() => {})
  classStore.fetchOverview().catch(() => {})
  complianceStore.fetchDashboard().catch(() => {})
  enforcementStore.fetchSummary().catch(() => {})
  dashboardApi.getFleet().then((d) => { fleet.value = d }).catch((e) => { loadErrors.value.push(e instanceof Error ? e.message : 'Failed to load fleet stats') })
  dashboardApi.getApps().then((d) => { apps.value = d }).catch((e) => { loadErrors.value.push(e instanceof Error ? e.message : 'Failed to load app stats') })
  dashboardApi.getFingerprinting().then((d) => { fingerprinting.value = d }).catch((e) => { loadErrors.value.push(e instanceof Error ? e.message : 'Failed to load fingerprinting stats') })
})

function triggerSync() {
  syncStore.triggerSync('full')
  router.push('/sync')
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function pct(part: number, total: number) {
  return total ? Math.round((part / total) * 100) : 0
}

function fmtNum(n: number | undefined) {
  if (n === undefined) return '—'
  return n.toLocaleString()
}

function distBar(record: Record<string, number>, key: string) {
  const total = Object.values(record).reduce((s, v) => s + v, 0)
  return pct(record[key] ?? 0, total)
}

// OS colours
const osColor: Record<string, string> = {
  windows: 'bg-[var(--info-bg)]0',
  macos: 'bg-[var(--text-3)]',
  linux: 'bg-[var(--warn-text)]',
}
// Machine type colours
const mtColor: Record<string, string> = {
  desktop: 'bg-[var(--brand-primary)]',
  laptop: 'bg-[var(--accent-text)]',
  server: 'bg-[var(--scope-site-bg)]0',
  vm: 'bg-cyan-400',
}

// Agent status colours
const nsColor: Record<string, string> = {
  online: 'bg-[var(--success-bg)]0',
  offline: 'bg-rose-400',
  degraded: 'bg-[var(--status-warn-text)]',
}

// Classification bars
const classificationBars = [
  { label: 'Correct',        key: 'correct'        as const, color: 'bg-[var(--success-bg)]0', track: 'bg-[var(--success-bg)]0/10' },
  { label: 'Misclassified',  key: 'misclassified'  as const, color: 'bg-[var(--status-warn-text)]',   track: 'bg-[var(--warn-bg)]0/10'   },
  { label: 'Ambiguous',      key: 'ambiguous'       as const, color: 'bg-[var(--warn-text)]',  track: 'bg-[var(--warn-bg)]0/10'  },
  { label: 'Unclassifiable', key: 'unclassifiable' as const, color: 'bg-[var(--text-3)]',   track: 'bg-[var(--badge-bg)]'   },
]

// Risk level colours
const riskColor: Record<string, string> = {
  critical: 'bg-[var(--error-bg)]0',
  high: 'bg-rose-400',
  medium: 'bg-[var(--status-warn-text)]',
  low: 'bg-[var(--status-ok-text)]',
  none: 'bg-[var(--text-3)]',
}
</script>

<template>
  <div class="p-6 max-w-[1400px] mx-auto space-y-6">

    <!-- Error banner -->
    <div v-if="loadErrors.length > 0" class="rounded-xl px-5 py-3 text-[12px] font-medium text-[var(--warn-text)] bg-[var(--warn-bg)] border border-[var(--warn-border)]">
      <p v-for="(err, i) in loadErrors" :key="i">{{ err }}</p>
    </div>

    <!-- ── Top stat cards ──────────────────────────────────────────────────── -->
    <div class="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-6 gap-4" aria-live="polite">
      <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);" aria-label="Agents count">
        <p class="text-[10px] font-semibold uppercase tracking-widest mb-2" style="color: var(--text-3);">Agents</p>
        <p class="text-[28px] font-bold leading-none tabular-nums" style="color: var(--text-1);">{{ fmtNum(fleet?.total_agents) }}</p>
      </div>
      <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);" aria-label="Groups count">
        <p class="text-[10px] font-semibold uppercase tracking-widest mb-2" style="color: var(--text-3);">Groups</p>
        <p class="text-[28px] font-bold leading-none tabular-nums" style="color: var(--text-1);">{{ fmtNum(fleet?.total_groups) }}</p>
      </div>
      <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);" aria-label="Sites count">
        <p class="text-[10px] font-semibold uppercase tracking-widest mb-2" style="color: var(--text-3);">Sites</p>
        <p class="text-[28px] font-bold leading-none tabular-nums" style="color: var(--text-1);">{{ fmtNum(fleet?.total_sites) }}</p>
      </div>
      <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);" aria-label="Distinct apps count">
        <p class="text-[10px] font-semibold uppercase tracking-widest mb-2" style="color: var(--text-3);">Distinct Apps</p>
        <p class="text-[28px] font-bold leading-none tabular-nums" style="color: var(--text-1);">{{ fmtNum(apps?.distinct_apps) }}</p>
      </div>
      <div class="rounded-xl p-4" :class="(classStore.overview?.misclassified ?? 0) + (classStore.overview?.ambiguous ?? 0) > 0 ? 'bg-[var(--warn-bg)] border-[var(--warn-border)]' : ''" :style="(classStore.overview?.misclassified ?? 0) + (classStore.overview?.ambiguous ?? 0) > 0 ? '' : 'background: var(--surface); border: 1px solid var(--border);'" aria-label="Anomalies count">
        <p class="text-[10px] font-semibold uppercase tracking-widest mb-2" :class="(classStore.overview?.misclassified ?? 0) + (classStore.overview?.ambiguous ?? 0) > 0 ? 'text-[var(--warn-text)]' : ''" :style="(classStore.overview?.misclassified ?? 0) + (classStore.overview?.ambiguous ?? 0) > 0 ? '' : 'color: var(--text-3);'">Anomalies</p>
        <p class="text-[28px] font-bold leading-none tabular-nums" :class="(classStore.overview?.misclassified ?? 0) + (classStore.overview?.ambiguous ?? 0) > 0 ? 'text-[var(--warn-text)]' : ''" :style="(classStore.overview?.misclassified ?? 0) + (classStore.overview?.ambiguous ?? 0) > 0 ? '' : 'color: var(--text-1);'">
          {{ classStore.overview ? fmtNum(classStore.overview.misclassified + classStore.overview.ambiguous) : '—' }}
        </p>
      </div>
      <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);" aria-label="Last sync time">
        <p class="text-[10px] font-semibold uppercase tracking-widest mb-2" style="color: var(--text-3);">Last Sync</p>
        <p class="text-[15px] font-bold leading-none" style="color: var(--text-1);">{{ formatRelativeTime(syncStore.lastCompletedRun?.completed_at) }}</p>
      </div>
    </div>

    <!-- ── Compliance & Enforcement summary ────────────────────────────── -->
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <!-- Compliance -->
      <router-link
        to="/compliance"
        class="rounded-xl p-4 transition-all hover:shadow-md block"
        style="background: var(--surface); border: 1px solid var(--border); text-decoration: none;"
      >
        <div class="flex items-center justify-between mb-2">
          <p class="text-[10px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Compliance Score</p>
          <span
            v-if="complianceViolations > 0"
            class="text-[10px] font-medium px-1.5 py-0.5 rounded-full"
            style="background: rgba(239, 68, 68, 0.15); color: var(--error-text);"
          >{{ complianceViolations }} violation{{ complianceViolations !== 1 ? 's' : '' }}</span>
        </div>
        <p
          class="text-[28px] font-bold leading-none tabular-nums"
          :style="{ color: complianceScore === null ? 'var(--text-3)' : complianceScore >= 90 ? 'var(--success-text)' : complianceScore >= 70 ? 'var(--warn-text)' : 'var(--error-text)' }"
        >
          {{ complianceScore !== null ? complianceScore + '%' : '—' }}
        </p>
        <p class="text-[11px] mt-1" style="color: var(--text-3);">
          {{ complianceStore.dashboard?.frameworks.length ?? 0 }} framework{{ (complianceStore.dashboard?.frameworks.length ?? 0) !== 1 ? 's' : '' }} active
        </p>
      </router-link>

      <!-- Enforcement -->
      <router-link
        to="/enforcement"
        class="rounded-xl p-4 transition-all hover:shadow-md block"
        style="background: var(--surface); border: 1px solid var(--border); text-decoration: none;"
      >
        <div class="flex items-center justify-between mb-2">
          <p class="text-[10px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Enforcement Rules</p>
          <span
            v-if="enforcementViolations > 0"
            class="text-[10px] font-medium px-1.5 py-0.5 rounded-full"
            style="background: rgba(239, 68, 68, 0.15); color: var(--error-text);"
          >{{ enforcementViolations }} violation{{ enforcementViolations !== 1 ? 's' : '' }}</span>
        </div>
        <div class="flex items-baseline gap-3">
          <p class="text-[28px] font-bold leading-none tabular-nums" style="color: var(--success-text);">{{ enforcementPassing }}</p>
          <span class="text-[13px]" style="color: var(--text-3);">pass</span>
          <p
            class="text-[28px] font-bold leading-none tabular-nums"
            :style="{ color: enforcementFailing > 0 ? 'var(--error-text)' : 'var(--text-3)' }"
          >{{ enforcementFailing }}</p>
          <span class="text-[13px]" style="color: var(--text-3);">fail</span>
        </div>
        <p class="text-[11px] mt-1" style="color: var(--text-3);">
          {{ enforcementStore.summary?.total_rules ?? 0 }} rule{{ (enforcementStore.summary?.total_rules ?? 0) !== 1 ? 's' : '' }} configured
        </p>
      </router-link>
    </div>

    <!-- ── Main grid ───────────────────────────────────────────────────────── -->
    <div class="grid grid-cols-3 gap-4">

      <!-- Fleet: OS distribution -->
      <div class="rounded-xl p-5" style="background: var(--surface); border: 1px solid var(--border);">
        <h2 class="text-[12px] font-semibold mb-4" style="color: var(--text-2);">OS Distribution</h2>
        <div v-if="fleet" class="space-y-2.5" aria-live="polite">
          <div
            v-for="[os, count] in Object.entries(fleet.os_distribution).sort((a,b) => b[1]-a[1])"
            :key="os"
            class="flex items-center gap-3"
          >
            <span class="w-20 text-[12px] capitalize shrink-0" style="color: var(--text-3);">{{ os }}</span>
            <div class="flex-1 h-2 rounded-full overflow-hidden" style="background: var(--surface-hover);"
              role="progressbar" :aria-valuenow="distBar(fleet.os_distribution, os)" aria-valuemin="0" aria-valuemax="100" :aria-label="`${os} distribution`">
              <div class="h-full rounded-full transition-all duration-500"
                :class="osColor[os] ?? 'bg-[var(--text-3)]'"
                :style="{ width: `${distBar(fleet.os_distribution, os)}%` }" />
            </div>
            <span class="w-14 text-right text-[12px] font-medium tabular-nums shrink-0" style="color: var(--text-2);">{{ fmtNum(count) }}</span>
          </div>
        </div>
        <div v-else class="h-20 flex items-center justify-center text-[12px]" style="color: var(--text-3);">Loading…</div>
      </div>

      <!-- Fleet: Machine types -->
      <div class="rounded-xl p-5" style="background: var(--surface); border: 1px solid var(--border);">
        <h2 class="text-[12px] font-semibold mb-4" style="color: var(--text-2);">Machine Types</h2>
        <div v-if="fleet" class="space-y-2.5" aria-live="polite">
          <div
            v-for="[mt, count] in Object.entries(fleet.machine_type).sort((a,b) => b[1]-a[1])"
            :key="mt"
            class="flex items-center gap-3"
          >
            <span class="w-20 text-[12px] capitalize shrink-0" style="color: var(--text-3);">{{ mt }}</span>
            <div class="flex-1 h-2 rounded-full overflow-hidden" style="background: var(--surface-hover);"
              role="progressbar" :aria-valuenow="distBar(fleet.machine_type, mt)" aria-valuemin="0" aria-valuemax="100" :aria-label="`${mt} distribution`">
              <div class="h-full rounded-full transition-all duration-500"
                :class="mtColor[mt] ?? 'bg-[var(--text-3)]'"
                :style="{ width: `${distBar(fleet.machine_type, mt)}%` }" />
            </div>
            <span class="w-14 text-right text-[12px] font-medium tabular-nums shrink-0" style="color: var(--text-2);">{{ fmtNum(count) }}</span>
          </div>
        </div>
        <div v-else class="h-20 flex items-center justify-center text-[12px]" style="color: var(--text-3);">Loading…</div>
      </div>

      <!-- Fleet: Network status + Stale agents -->
      <div class="rounded-xl p-5" style="background: var(--surface); border: 1px solid var(--border);">
        <h2 class="text-[12px] font-semibold mb-4" style="color: var(--text-2);">Agent Status</h2>
        <div v-if="fleet" class="space-y-2.5 mb-5" aria-live="polite">
          <div
            v-for="[ns, count] in Object.entries(fleet.agent_status).sort((a,b) => b[1]-a[1])"
            :key="ns"
            class="flex items-center gap-3"
          >
            <span class="w-24 text-[12px] capitalize shrink-0" style="color: var(--text-3);">{{ ns }}</span>
            <div class="flex-1 h-2 rounded-full overflow-hidden" style="background: var(--surface-hover);"
              role="progressbar" :aria-valuenow="distBar(fleet.agent_status, ns)" aria-valuemin="0" aria-valuemax="100" :aria-label="`${ns} agent status`">
              <div class="h-full rounded-full transition-all duration-500"
                :class="nsColor[ns] ?? 'bg-[var(--text-3)]'"
                :style="{ width: `${distBar(fleet.agent_status, ns)}%` }" />
            </div>
            <span class="w-14 text-right text-[12px] font-medium tabular-nums shrink-0" style="color: var(--text-2);">{{ fmtNum(count) }}</span>
          </div>
        </div>

        <!-- Stale agents -->
        <h2 class="text-[12px] font-semibold mb-3" style="color: var(--text-2);">Stale Agents</h2>
        <div v-if="fleet" class="space-y-1.5" aria-live="polite">
          <div v-for="[label, val] in [['> 7 days', fleet.stale_7d], ['> 14 days', fleet.stale_14d], ['> 30 days', fleet.stale_30d]]" :key="label" class="flex items-center justify-between">
            <span class="text-[12px]" style="color: var(--text-3);">{{ label }}</span>
            <span class="text-[12px] font-semibold tabular-nums" :class="(val as number) > 0 ? 'text-[var(--error-text)]' : ''" :style="(val as number) > 0 ? '' : 'color: var(--text-3);'">
              {{ fmtNum(val as number) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- ── App intelligence + Classification + Fingerprinting ─────────────── -->
    <div class="grid grid-cols-3 gap-4">

      <!-- Top 10 apps -->
      <div class="rounded-xl p-5" style="background: var(--surface); border: 1px solid var(--border);">
        <h2 class="text-[12px] font-semibold mb-1" style="color: var(--text-2);">Top Apps by Fleet Coverage</h2>
        <p class="text-[11px] mb-4" style="color: var(--text-3);">% of agents with the app installed</p>
        <div v-if="apps?.top_apps.length" class="space-y-2" aria-live="polite">
          <div v-for="app in apps.top_apps" :key="app.normalized_name" class="flex items-center gap-2">
            <span class="flex-1 text-[11px] truncate" style="color: var(--text-2);">{{ app.display_name }}</span>
            <div class="w-20 h-1.5 rounded-full overflow-hidden shrink-0" style="background: var(--surface-hover);"
              role="progressbar" :aria-valuenow="Math.round(app.coverage * 100)" aria-valuemin="0" aria-valuemax="100" :aria-label="`${app.display_name} fleet coverage`">
              <div class="h-full rounded-full bg-[var(--brand-primary-light)] transition-all duration-500"
                :style="{ width: `${Math.round(app.coverage * 100)}%` }" />
            </div>
            <span class="w-9 text-right text-[11px] font-medium tabular-nums shrink-0" style="color: var(--text-3);">{{ Math.round(app.coverage * 100) }}%</span>
          </div>
        </div>
        <div v-else class="h-20 flex items-center justify-center text-[12px]" style="color: var(--text-3);">No data</div>
      </div>

      <!-- Publishers + App stats -->
      <div class="rounded-xl p-5 space-y-5" style="background: var(--surface); border: 1px solid var(--border);">

        <!-- App stats row -->
        <div v-if="apps" aria-live="polite">
          <h2 class="text-[12px] font-semibold mb-3" style="color: var(--text-2);">App Stats</h2>
          <div class="grid grid-cols-3 gap-3">
            <div class="rounded-lg px-3 py-2.5 text-center" style="background: var(--surface-inset);" aria-label="Distinct apps count">
              <p class="text-[20px] font-bold tabular-nums" style="color: var(--text-1);">{{ fmtNum(apps.distinct_apps) }}</p>
              <p class="text-[10px] mt-0.5" style="color: var(--text-3);">Distinct apps</p>
            </div>
            <div class="rounded-lg px-3 py-2.5 text-center" style="background: var(--surface-inset);" aria-label="Average apps per agent">
              <p class="text-[20px] font-bold tabular-nums" style="color: var(--text-1);">{{ apps.avg_apps_per_agent }}</p>
              <p class="text-[10px] mt-0.5" style="color: var(--text-3);">Avg per agent</p>
            </div>
            <div class="rounded-lg bg-[var(--warn-bg)] px-3 py-2.5 text-center" aria-label="Unique apps installed on only one agent">
              <p class="text-[20px] font-bold text-[var(--warn-text)] tabular-nums">{{ fmtNum(apps.unique_apps) }}</p>
              <p class="text-[10px] text-[var(--warn-text)] mt-0.5">Unique (1 agent)</p>
            </div>
          </div>
        </div>

        <!-- Top publishers -->
        <div>
          <h2 class="text-[12px] font-semibold mb-3" style="color: var(--text-2);">Top Publishers</h2>
          <div v-if="apps?.top_publishers.length" class="space-y-1.5">
            <div v-for="pub in apps.top_publishers.slice(0, 7)" :key="pub.publisher" class="flex items-center justify-between gap-2">
              <span class="text-[11px] truncate flex-1" style="color: var(--text-2);">{{ pub.publisher }}</span>
              <span class="text-[11px] font-medium tabular-nums shrink-0" style="color: var(--text-3);">{{ pub.app_count }} apps</span>
            </div>
          </div>
          <div v-else class="text-[12px]" style="color: var(--text-3);">No publisher data</div>
        </div>

        <!-- Risk distribution -->
        <div v-if="apps && Object.keys(apps.risk_distribution).length">
          <h2 class="text-[12px] font-semibold mb-3" style="color: var(--text-2);">Risk Levels</h2>
          <div class="flex gap-2 flex-wrap">
            <div
              v-for="[level, count] in Object.entries(apps.risk_distribution).sort((a,b) => b[1]-a[1])"
              :key="level"
              class="flex items-center gap-1.5 px-2 py-1 rounded-lg"
              style="background: var(--surface-inset); border: 1px solid var(--border-light);"
            >
              <span class="w-2 h-2 rounded-full shrink-0" :class="riskColor[level] ?? 'bg-[var(--text-3)]'" aria-hidden="true" />
              <span class="text-[11px] capitalize" style="color: var(--text-2);">{{ level }}</span>
              <span class="text-[11px] font-semibold tabular-nums" style="color: var(--text-2);">{{ fmtNum(count) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right column: Classification + Fingerprinting + Actions -->
      <div class="space-y-4">

        <!-- Classification overview -->
        <div class="rounded-xl p-5" style="background: var(--surface); border: 1px solid var(--border);">
          <h2 class="text-[12px] font-semibold mb-4" style="color: var(--text-2);">Classification</h2>
          <div v-if="classStore.overview" class="space-y-2.5" aria-live="polite">
            <div v-for="bar in classificationBars" :key="bar.key" class="flex items-center gap-3">
              <span class="w-24 text-[11px] shrink-0" style="color: var(--text-3);">{{ bar.label }}</span>
              <div class="flex-1 h-2 rounded-full overflow-hidden" :class="bar.track"
                role="progressbar" :aria-valuenow="classStore.overview.total ? pct(classStore.overview[bar.key], classStore.overview.total) : 0" aria-valuemin="0" aria-valuemax="100" :aria-label="`${bar.label} classification`">
                <div class="h-full rounded-full transition-all duration-500" :class="bar.color"
                  :style="{ width: classStore.overview.total ? `${pct(classStore.overview[bar.key], classStore.overview.total)}%` : '0%' }" />
              </div>
              <span class="w-14 text-right text-[11px] font-medium tabular-nums shrink-0" style="color: var(--text-2);">
                {{ fmtNum(classStore.overview[bar.key]) }}
              </span>
            </div>
          </div>
          <div v-else class="text-[12px] text-center py-4" style="color: var(--text-3);">Run a sync to classify agents.</div>
        </div>

        <!-- Fingerprinting progress -->
        <div class="rounded-xl p-5" style="background: var(--surface); border: 1px solid var(--border);">
          <h2 class="text-[12px] font-semibold mb-4" style="color: var(--text-2);">Fingerprinting</h2>
          <div v-if="fingerprinting" class="space-y-3" aria-live="polite">
            <!-- Coverage bar -->
            <div>
              <div class="flex justify-between text-[11px] mb-1" style="color: var(--text-3);">
                <span>Groups fingerprinted</span>
                <span class="font-semibold" style="color: var(--text-2);">{{ fingerprinting.groups_with_fingerprint }} / {{ fingerprinting.total_groups }}</span>
              </div>
              <div class="h-2 rounded-full overflow-hidden" style="background: var(--surface-hover);"
                role="progressbar" :aria-valuenow="pct(fingerprinting.groups_with_fingerprint, fingerprinting.total_groups)" aria-valuemin="0" aria-valuemax="100" aria-label="Groups fingerprinted progress">
                <div class="h-full rounded-full bg-[var(--brand-primary)] transition-all duration-500"
                  :style="{ width: `${pct(fingerprinting.groups_with_fingerprint, fingerprinting.total_groups)}%` }" />
              </div>
            </div>
            <div class="grid grid-cols-2 gap-2 pt-1">
              <div class="rounded-lg px-3 py-2 text-center" style="background: var(--surface-inset);">
                <p class="text-[18px] font-bold tabular-nums" style="color: var(--text-1);">{{ fingerprinting.avg_markers_per_fingerprint }}</p>
                <p class="text-[10px]" style="color: var(--text-3);">Avg markers</p>
              </div>
              <div class="rounded-lg px-3 py-2 text-center" :class="fingerprinting.thin_fingerprints > 0 ? 'bg-[var(--warn-bg)]' : ''" :style="fingerprinting.thin_fingerprints > 0 ? '' : 'background: var(--surface-inset);'">
                <p class="text-[18px] font-bold tabular-nums" :class="fingerprinting.thin_fingerprints > 0 ? 'text-[var(--warn-text)]' : ''" :style="fingerprinting.thin_fingerprints > 0 ? '' : 'color: var(--text-1);'">{{ fingerprinting.thin_fingerprints }}</p>
                <p class="text-[10px]" :class="fingerprinting.thin_fingerprints > 0 ? 'text-[var(--warn-text)]' : ''" :style="fingerprinting.thin_fingerprints > 0 ? '' : 'color: var(--text-3);'">Thin (&lt;3 markers)</p>
              </div>
              <div class="rounded-lg px-3 py-2 text-center" :class="fingerprinting.pending_proposals > 0 ? 'bg-[var(--brand-primary-light)]' : ''" :style="fingerprinting.pending_proposals > 0 ? '' : 'background: var(--surface-inset);'">
                <p class="text-[18px] font-bold tabular-nums" :class="fingerprinting.pending_proposals > 0 ? 'text-[var(--brand-primary)]' : ''" :style="fingerprinting.pending_proposals > 0 ? '' : 'color: var(--text-1);'">{{ fingerprinting.pending_proposals }}</p>
                <p class="text-[10px]" :class="fingerprinting.pending_proposals > 0 ? 'text-[var(--brand-primary-light)]' : ''" :style="fingerprinting.pending_proposals > 0 ? '' : 'color: var(--text-3);'">Pending proposals</p>
              </div>
              <div class="rounded-lg bg-[var(--error-bg)] px-3 py-2 text-center" v-if="fingerprinting.groups_without_fingerprint > 0">
                <p class="text-[18px] font-bold text-[var(--error-text)] tabular-nums">{{ fingerprinting.groups_without_fingerprint }}</p>
                <p class="text-[10px] text-[var(--error-text)]">No fingerprint</p>
              </div>
              <div class="rounded-lg px-3 py-2 text-center" style="background: var(--surface-inset);" v-else>
                <p class="text-[18px] font-bold text-[var(--success-text)] tabular-nums">✓</p>
                <p class="text-[10px]" style="color: var(--text-3);">All covered</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Quick actions -->
        <div class="rounded-xl p-5 flex flex-col gap-2" style="background: var(--surface); border: 1px solid var(--border);">
          <h2 class="text-[12px] font-semibold mb-1" style="color: var(--text-2);">Quick Actions</h2>
          <button
            class="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-[var(--brand-primary)] hover:bg-[var(--brand-primary-dark)] text-white text-[12px] font-medium transition-colors"
            @click="triggerSync"
          >
            <svg class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Sync Now
          </button>
          <router-link to="/anomalies" aria-label="View Anomalies" class="flex items-center gap-2 px-3 py-2.5 rounded-lg text-[12px] font-medium transition-colors no-underline" style="border: 1px solid var(--border); color: var(--text-2);">
            <svg class="w-4 h-4 shrink-0 text-[var(--warn-text)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            View Anomalies
          </router-link>
          <router-link to="/fingerprints/proposals" aria-label="Fingerprint Proposals" class="flex items-center gap-2 px-3 py-2.5 rounded-lg text-[12px] font-medium transition-colors no-underline" style="border: 1px solid var(--border); color: var(--text-2);">
            <svg class="w-4 h-4 shrink-0 text-[var(--brand-primary-light)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            Fingerprint Proposals
          </router-link>
          <router-link to="/fingerprints" aria-label="Fingerprint Editor" class="flex items-center gap-2 px-3 py-2.5 rounded-lg text-[12px] font-medium transition-colors no-underline" style="border: 1px solid var(--border); color: var(--text-2);">
            <svg class="w-4 h-4 shrink-0 text-[var(--text-3)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
            </svg>
            Fingerprint Editor
          </router-link>
        </div>

      </div>
    </div>

  </div>
</template>
