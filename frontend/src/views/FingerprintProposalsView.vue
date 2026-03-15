<!--
  Fingerprint Proposals — cross-group Lift-based marker blueprint dashboard.

  Layout:
  1. Page header — title, subtitle, Generate button, last-computed timestamp
  2. While generating — animated progress banner
  3. Summary stat bar — groups analyzed, markers proposed, conflicts, avg lift
  4. Filter/sort bar + "Apply All Pending" bulk action
  5. Proposal cards (one per group, sorted by quality score desc)
     - Collapsed: quality ring, group name, marker count, conflict badge, Apply/Dismiss
     - Expanded: per-marker table with coverage mini-bars and lift chips
-->
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import * as fingerprintsApi from '@/api/fingerprints'
import type { AutoFingerprintProposal, ProposedMarker } from '@/types/fingerprint'
import { formatDateTime } from '@/utils/formatters'

const router = useRouter()

// ── State ────────────────────────────────────────────────────────────────────

const proposals = ref<AutoFingerprintProposal[]>([])
const isLoading = ref(true)
const isGenerating = ref(false)
const error = ref<string | null>(null)
const toast = ref<{ msg: string; type: 'success' | 'error' } | null>(null)
const expandedGroups = ref<Set<string>>(new Set())
const applyingGroups = ref<Set<string>>(new Set())
const dismissingGroups = ref<Set<string>>(new Set())
const markerSearch = ref<Record<string, string>>({})
const addingMarkers = ref<Set<string>>(new Set())  // "groupId:normalizedName"
const addedMarkers = ref<Set<string>>(new Set())   // "groupId:normalizedName"
const isApplyingAll = ref(false)
const mounted = ref(true)
let toastTimeout: ReturnType<typeof setTimeout> | null = null

type MarkerSortKey = 'lift' | 'name' | 'in_group' | 'outside'
type MarkerSortDir = 'asc' | 'desc'
const markerSortKey = ref<MarkerSortKey>('lift')
const markerSortDir = ref<MarkerSortDir>('desc')

function setMarkerSort(key: MarkerSortKey) {
  if (markerSortKey.value === key) {
    markerSortDir.value = markerSortDir.value === 'desc' ? 'asc' : 'desc'
  } else {
    markerSortKey.value = key
    markerSortDir.value = key === 'name' ? 'asc' : 'desc'
  }
}

function sortedFilteredMarkers(proposal: AutoFingerprintProposal) {
  const q = (markerSearch.value[proposal.group_id] ?? '').toLowerCase().trim()
  let list = q
    ? proposal.proposed_markers.filter(
        (m) => m.display_name.toLowerCase().includes(q) || m.normalized_name.includes(q),
      )
    : [...proposal.proposed_markers]
  const dir = markerSortDir.value === 'asc' ? 1 : -1
  list.sort((a, b) => {
    switch (markerSortKey.value) {
      case 'name':     return dir * a.display_name.localeCompare(b.display_name)
      case 'in_group': return dir * (a.group_coverage - b.group_coverage)
      case 'outside':  return dir * (a.outside_coverage - b.outside_coverage)
      case 'lift':
      default:         return dir * (a.lift - b.lift)
    }
  })
  return list
}

type FilterKey = 'all' | 'high' | 'conflicts' | 'applied' | 'dismissed'
const activeFilter = ref<FilterKey>('all')
type SortKey = 'quality' | 'name'
const sortKey = ref<SortKey>('quality')

// Hide groups whose agent count is below this threshold (0 = show all)
const minGroupSize = ref(5)
const hideSmallGroups = ref(true)

// ── Load ──────────────────────────────────────────────────────────────────────

onMounted(async () => {
  await loadProposals()
})

onUnmounted(() => {
  mounted.value = false
  if (toastTimeout) clearTimeout(toastTimeout)
})

async function loadProposals() {
  isLoading.value = true
  error.value = null
  try {
    proposals.value = await fingerprintsApi.listProposals(activeFilter.value === 'dismissed')
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load proposals'
  } finally {
    isLoading.value = false
  }
}

// ── Generate ──────────────────────────────────────────────────────────────────

async function generate() {
  if (isGenerating.value) return
  isGenerating.value = true
  error.value = null
  try {
    await fingerprintsApi.generateProposals()
    // Poll until the run completes (backend runs it as a background task)
    await pollUntilDone()
    await loadProposals()
    showToast('Proposals generated successfully', 'success')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : 'Generation failed'
    if (msg.includes('409') || msg.includes('already running')) {
      showToast('Generation already running — please wait', 'error')
    } else {
      showToast(msg, 'error')
    }
  } finally {
    isGenerating.value = false
  }
}

async function pollUntilDone(maxMs = 120_000, intervalMs = 1500) {
  const deadline = Date.now() + maxMs
  while (Date.now() < deadline) {
    if (!mounted.value) return
    await delay(intervalMs)
    if (!mounted.value) return
    // Try fetching — if count changed or computed_at changed we're done
    const fresh = await fingerprintsApi.listProposals(false)
    if (fresh.length > 0) {
      const prevAt = proposals.value[0]?.computed_at
      const freshAt = fresh[0]?.computed_at
      if (freshAt !== prevAt) {
        proposals.value = fresh
        return
      }
    }
  }
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// ── Apply / dismiss ───────────────────────────────────────────────────────────

async function applyProposal(groupId: string) {
  applyingGroups.value.add(groupId)
  try {
    const result = await fingerprintsApi.applyProposal(groupId)
    // Update local state
    const p = proposals.value.find((x) => x.group_id === groupId)
    if (p) p.status = 'applied'
    showToast(`Applied ${result.added} marker${result.added !== 1 ? 's' : ''} (${result.skipped} skipped)`, 'success')
  } catch (e) {
    showToast(e instanceof Error ? e.message : 'Apply failed', 'error')
  } finally {
    applyingGroups.value.delete(groupId)
  }
}

async function addSingleMarker(groupId: string, marker: ProposedMarker) {
  const key = `${groupId}:${marker.normalized_name}`
  if (addingMarkers.value.has(key) || addedMarkers.value.has(key)) return
  addingMarkers.value.add(key)
  try {
    await fingerprintsApi.addMarker(groupId, {
      pattern: marker.normalized_name,
      display_name: marker.display_name,
      category: 'application',
      source: 'statistical',
      weight: 1.0,
    })
    addedMarkers.value.add(key)
    showToast(`Added "${marker.display_name}"`, 'success')
  } catch (e) {
    showToast(e instanceof Error ? e.message : 'Failed to add marker', 'error')
  } finally {
    addingMarkers.value.delete(key)
  }
}

async function dismissProposal(groupId: string) {
  dismissingGroups.value.add(groupId)
  try {
    await fingerprintsApi.dismissProposal(groupId)
    proposals.value = proposals.value.filter((p) => p.group_id !== groupId)
  } catch (e) {
    showToast(e instanceof Error ? e.message : 'Dismiss failed', 'error')
  } finally {
    dismissingGroups.value.delete(groupId)
  }
}

async function applyAll() {
  if (isApplyingAll.value) return
  isApplyingAll.value = true
  try {
    const pending = filteredProposals.value.filter((p) => p.status === 'pending')
    for (const p of pending) {
      await applyProposal(p.group_id)
    }
  } finally {
    isApplyingAll.value = false
  }
}

// ── Filter / sort / expand ────────────────────────────────────────────────────

function toggleExpand(groupId: string) {
  if (expandedGroups.value.has(groupId)) {
    expandedGroups.value.delete(groupId)
  } else {
    expandedGroups.value.add(groupId)
  }
}

const filteredProposals = computed(() => {
  let list = proposals.value

  // Small-group filter
  if (hideSmallGroups.value && minGroupSize.value > 0) {
    list = list.filter((p) => p.group_size >= minGroupSize.value)
  }

  if (activeFilter.value === 'high') list = list.filter((p) => p.quality_score >= 8)
  else if (activeFilter.value === 'conflicts') list = list.filter((p) => hasConflicts(p))
  else if (activeFilter.value === 'applied') list = list.filter((p) => p.status === 'applied')
  else if (activeFilter.value === 'dismissed') list = list.filter((p) => p.status === 'dismissed')

  if (sortKey.value === 'name') return [...list].sort((a, b) => a.group_name.localeCompare(b.group_name))
  return [...list].sort((a, b) => b.quality_score - a.quality_score)
})

function hasConflicts(p: AutoFingerprintProposal) {
  return p.proposed_markers.some((m) => m.shared_with_groups.length > 0)
}

function conflictCount(p: AutoFingerprintProposal) {
  return p.proposed_markers.filter((m) => m.shared_with_groups.length > 0).length
}

// ── Summary stats ─────────────────────────────────────────────────────────────

const totalGroups = computed(() => proposals.value[0]?.total_groups ?? proposals.value.length)

const groupNameMap = computed(() =>
  Object.fromEntries(proposals.value.map((p) => [p.group_id, p.group_name])),
)

const totalMarkers = computed(() =>
  proposals.value.reduce((s, p) => s + p.proposed_markers.length, 0),
)

const totalConflicts = computed(() =>
  proposals.value.reduce((s, p) => s + conflictCount(p), 0),
)

const avgLift = computed(() => {
  if (!proposals.value.length) return 0
  const sum = proposals.value.reduce((s, p) => s + p.quality_score, 0)
  return sum / proposals.value.length
})

const lastComputedAt = computed(() => proposals.value[0]?.computed_at ?? null)

// ── Quality ring helpers ──────────────────────────────────────────────────────

/** Normalise quality score to 0–100% for display. Max meaningful lift = 20. */
function qualityPct(score: number) {
  return Math.min(100, Math.round((score / 20) * 100))
}

function qualityColor(score: number) {
  if (score >= 8) return '#10b981'   // emerald
  if (score >= 4) return '#f59e0b'   // amber
  return '#ef4444'                    // red
}

function ringDashArray(score: number) {
  const pct = qualityPct(score) / 100
  const circumference = 2 * Math.PI * 18 // r=18
  return `${circumference * pct} ${circumference * (1 - pct)}`
}

// ── Lift chip color ───────────────────────────────────────────────────────────

function liftChipClass(lift: number) {
  if (lift >= 10) return 'bg-teal-50 text-teal-700 border border-teal-200'
  if (lift >= 5)  return 'bg-indigo-50 text-indigo-700 border border-indigo-200'
  return 'badge-neutral border'
}

function formatLift(lift: number): string {
  if (lift >= 99) return '>99×'
  if (Number.isInteger(lift)) return `${lift}×`
  return `${lift.toFixed(1)}×`
}

function expandAll() {
  expandedGroups.value = new Set(filteredProposals.value.map((p) => p.group_id))
}
function collapseAll() {
  expandedGroups.value = new Set()
}

// ── Toast ────────────────────────────────────────────────────────────────────

function showToast(msg: string, type: 'success' | 'error') {
  toast.value = { msg, type }
  if (toastTimeout) clearTimeout(toastTimeout)
  toastTimeout = setTimeout(() => { toast.value = null }, 3500)
}
</script>

<template>
  <div class="p-6 max-w-[960px] space-y-5">

    <!-- Toast -->
    <transition name="fade">
      <div
        v-if="toast"
        class="fixed top-5 right-5 z-50 flex items-center gap-2.5 px-4 py-3 rounded-xl shadow-lg text-[13px] font-medium"
        :class="toast.type === 'success'
          ? 'bg-emerald-50 border border-emerald-200 text-emerald-800'
          : 'bg-red-50 border border-red-200 text-red-800'"
      >
        <svg v-if="toast.type === 'success'" class="w-4 h-4 text-emerald-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <svg v-else class="w-4 h-4 text-red-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        {{ toast.msg }}
      </div>
    </transition>

    <!-- ── Page header ── -->
    <div class="flex items-start justify-between gap-4">
      <div>
        <h1 class="text-[20px] font-bold leading-tight" style="color: var(--heading);">Fingerprint Proposals</h1>
        <p class="text-[13px] mt-0.5" style="color: var(--text-3);">
          Lift-based marker blueprints — agents in a group are <em>N×</em> more likely to have each proposed app.
        </p>
      </div>
      <div class="flex items-center gap-3 shrink-0">
        <span v-if="lastComputedAt" class="text-[11px]" style="color: var(--text-3);">
          Last run {{ formatDateTime(lastComputedAt) }}
        </span>
        <button
          @click="generate"
          :disabled="isGenerating"
          aria-label="Generate fingerprint proposals"
          class="flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-semibold transition-all"
          :class="isGenerating
            ? 'bg-indigo-100 text-indigo-400 cursor-not-allowed'
            : 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm'"
        >
          <svg
            class="w-3.5 h-3.5"
            :class="isGenerating ? 'animate-spin' : ''"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"
            aria-hidden="true"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {{ isGenerating ? 'Generating…' : 'Generate Proposals' }}
        </button>
      </div>
    </div>

    <!-- ── Generating progress banner ── -->
    <div v-if="isGenerating" class="bg-indigo-50 border border-indigo-100 rounded-xl px-5 py-4">
      <div class="flex items-center gap-3 mb-2.5">
        <svg class="w-4 h-4 text-indigo-500 animate-spin shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        <span class="text-[13px] font-medium text-indigo-700">
          Analyzing installed applications across all groups…
        </span>
      </div>
      <div class="h-1.5 rounded-full bg-indigo-100 overflow-hidden">
        <div class="h-full bg-indigo-400 rounded-full animate-pulse" style="width: 60%;" />
      </div>
    </div>

    <!-- ── Loading ── -->
    <div v-if="isLoading" class="flex items-center justify-center py-24 text-[13px]" style="color: var(--text-3);">
      Loading…
    </div>

    <!-- ── Error ── -->
    <div v-else-if="error" class="flex items-center justify-center py-24 text-red-400 text-[13px]">
      {{ error }}
    </div>

    <!-- ── Empty state ── -->
    <div
      v-else-if="!isLoading && proposals.length === 0"
      class="rounded-xl px-6 py-16 text-center"
      style="background: var(--surface); border: 1px solid var(--border);"
    >
      <svg class="w-10 h-10 text-slate-200 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
      </svg>
      <p class="text-[14px] font-medium" style="color: var(--text-3);">No proposals yet</p>
      <p class="text-[12px] mt-1" style="color: var(--text-3);">Click "Generate Proposals" to analyse all groups.</p>
    </div>

    <template v-else-if="!isLoading">

      <!-- ── Summary stat bar ── -->
      <div class="grid grid-cols-4 gap-3">
        <div class="rounded-xl px-4 py-3.5" style="background: var(--surface); border: 1px solid var(--border);">
          <p class="text-[22px] font-bold leading-none" style="color: var(--heading);">{{ totalGroups }}</p>
          <p class="text-[11px] mt-1" style="color: var(--text-3);">Groups analyzed</p>
        </div>
        <div class="rounded-xl px-4 py-3.5" style="background: var(--surface); border: 1px solid var(--border);">
          <p class="text-[22px] font-bold leading-none" style="color: var(--heading);">{{ totalMarkers }}</p>
          <p class="text-[11px] mt-1" style="color: var(--text-3);">Markers proposed</p>
        </div>
        <div
          class="border rounded-xl px-4 py-3.5"
          :class="totalConflicts > 0
            ? 'bg-amber-50 border-amber-200'
            : ''"
          :style="totalConflicts > 0 ? '' : `background: var(--surface); border-color: var(--border);`"
        >
          <p
            class="text-[22px] font-bold leading-none"
            :class="totalConflicts > 0 ? 'text-amber-600' : ''"
            :style="totalConflicts > 0 ? '' : `color: var(--heading);`"
          >
            {{ totalConflicts }}
          </p>
          <p class="text-[11px] mt-1" style="color: var(--text-3);">Conflicts detected</p>
        </div>
        <div class="rounded-xl px-4 py-3.5" style="background: var(--surface); border: 1px solid var(--border);">
          <p class="text-[22px] font-bold leading-none" style="color: var(--heading);">{{ formatLift(avgLift) }}</p>
          <p class="text-[11px] mt-1" style="color: var(--text-3);">Avg lift</p>
        </div>
      </div>

      <!-- ── Filter / sort / bulk action bar ── -->
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <!-- Small-group filter toggle -->
        <div class="flex items-center gap-2 mr-2">
          <button
            role="switch"
            :aria-checked="hideSmallGroups"
            @click="hideSmallGroups = !hideSmallGroups"
            class="relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-1"
            :class="hideSmallGroups ? 'bg-indigo-600' : 'bg-gray-200'"
          >
            <span
              class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform"
              :class="hideSmallGroups ? 'translate-x-4' : 'translate-x-0'"
            />
          </button>
          <span class="text-[12px] whitespace-nowrap" style="color: var(--text-2);">
            Min
            <input
              type="number"
              v-model.number="minGroupSize"
              min="1"
              max="999"
              class="inline-block w-12 mx-1 text-center text-[12px] px-1 py-0.5 rounded focus:outline-none focus:ring-1 focus:ring-indigo-400"
              style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              :disabled="!hideSmallGroups"
              :class="!hideSmallGroups ? 'opacity-40 cursor-not-allowed' : ''"
            />
            agents
          </span>
        </div>
        <!-- Filter chips -->
        <div class="flex items-center gap-1.5 flex-wrap">
          <button
            v-for="f in ([
              { key: 'all',       label: 'All' },
              { key: 'high',      label: 'High quality (≥8×)' },
              { key: 'conflicts', label: 'Has conflicts' },
              { key: 'applied',   label: 'Applied' },
              { key: 'dismissed', label: 'Dismissed' },
            ] as const)"
            :key="f.key"
            @click="activeFilter = f.key; loadProposals()"
            :aria-pressed="activeFilter === f.key"
            class="px-3 py-1 rounded-full text-[12px] font-medium transition-colors"
            :class="activeFilter === f.key
              ? 'bg-indigo-600 text-white'
              : ''"
            :style="activeFilter === f.key
              ? 'border: 1px solid rgb(79 70 229);'
              : `background: var(--surface); color: var(--text-3); border: 1px solid var(--border);`"
          >
            {{ f.label }}
          </button>
        </div>
        <div class="flex items-center gap-2">
          <!-- Sort -->
          <select
            v-model="sortKey"
            class="text-[12px] px-2.5 py-1.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
            style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-2);"
          >
            <option value="quality">Sort: Quality ↓</option>
            <option value="name">Sort: Group name</option>
          </select>
          <!-- Expand / Collapse all -->
          <button
            @click="expandAll"
            aria-label="Expand all proposal cards"
            class="px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors"
            style="background: var(--surface); border: 1px solid var(--border); color: var(--text-2);"
          >↓ Expand all</button>
          <button
            @click="collapseAll"
            aria-label="Collapse all proposal cards"
            class="px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors"
            style="background: var(--surface); border: 1px solid var(--border); color: var(--text-2);"
          >↑ Collapse all</button>
          <!-- Apply All -->
          <button
            @click="applyAll"
            :disabled="isApplyingAll"
            aria-label="Apply all pending proposals"
            class="px-3 py-1.5 rounded-lg text-[12px] font-semibold bg-emerald-600 text-white hover:bg-emerald-700 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ isApplyingAll ? 'Applying…' : 'Apply All Pending' }}
          </button>
        </div>
      </div>

      <!-- ── Proposal cards ── -->
      <div class="space-y-3" aria-live="polite">
        <div
          v-for="proposal in filteredProposals"
          :key="proposal.group_id"
          class="rounded-xl overflow-hidden transition-all"
          :class="{
            'border-emerald-300': proposal.status === 'applied',
          }"
          :style="proposal.status === 'applied'
            ? 'background: var(--surface); border: 1px solid rgb(110 231 183);'
            : `background: var(--surface); border: 1px solid var(--border);`"
        >
          <!-- Card header -->
          <div
            class="flex items-center gap-4 px-5 py-4 cursor-pointer transition-colors select-none"
            :aria-expanded="expandedGroups.has(proposal.group_id)"
            @click="toggleExpand(proposal.group_id)"
          >
            <!-- Quality ring (SVG donut) -->
            <div class="shrink-0 relative w-12 h-12">
              <svg class="w-12 h-12 -rotate-90" viewBox="0 0 40 40" aria-hidden="true">
                <!-- Track -->
                <circle cx="20" cy="20" r="18" fill="none" stroke="#f1f5f9" stroke-width="3.5" />
                <!-- Progress -->
                <circle
                  cx="20" cy="20" r="18"
                  fill="none"
                  :stroke="qualityColor(proposal.quality_score)"
                  stroke-width="3.5"
                  stroke-linecap="round"
                  :stroke-dasharray="ringDashArray(proposal.quality_score)"
                />
              </svg>
              <!-- Center label -->
              <div class="absolute inset-0 flex items-center justify-center">
                <span class="text-[10px] font-bold leading-none" style="color: var(--text-2);">
                  {{ qualityPct(proposal.quality_score) }}%
                </span>
              </div>
            </div>

            <!-- Group info -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-[14px] font-semibold truncate" style="color: var(--heading);">
                  {{ proposal.group_name }}
                </span>
                <!-- Agent count badge -->
                <span class="text-[11px] font-medium px-1.5 py-0.5 rounded"
                  :class="proposal.group_size < 5
                    ? 'bg-amber-100 text-amber-700'
                    : ' text-muted'" style="background: var(--surface-hover);"
                  :title="proposal.group_size < 5 ? 'Group is too small for reliable proposals' : `${proposal.group_size} agents`"
                >
                  <svg v-if="proposal.group_size < 5" class="inline w-3 h-3 mr-0.5 -mt-0.5" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                    <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                  </svg>
                  {{ proposal.group_size ?? '?' }} agent{{ (proposal.group_size ?? 2) !== 1 ? 's' : '' }}
                </span>
                <!-- Applied badge -->
                <span
                  v-if="proposal.status === 'applied'"
                  class="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700"
                >
                  Applied
                </span>
              </div>
              <div class="flex items-center gap-3 mt-0.5 flex-wrap">
                <span class="text-[12px]" style="color: var(--text-3);">
                  {{ proposal.proposed_markers.length }} marker{{ proposal.proposed_markers.length !== 1 ? 's' : '' }}
                </span>
                <span class="text-[12px] font-medium text-indigo-600">
                  avg {{ formatLift(proposal.quality_score) }} lift
                </span>
                <!-- Conflict badge -->
                <span
                  v-if="conflictCount(proposal) > 0"
                  class="flex items-center gap-1 text-[11px] font-medium text-amber-600"
                >
                  <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                    <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                  </svg>
                  {{ conflictCount(proposal) }} conflict{{ conflictCount(proposal) !== 1 ? 's' : '' }}
                </span>
              </div>
            </div>

            <!-- Actions -->
            <div class="flex items-center gap-2 shrink-0" @click.stop>
              <button
                v-if="proposal.status !== 'applied'"
                @click="applyProposal(proposal.group_id)"
                :disabled="applyingGroups.has(proposal.group_id)"
                :aria-label="`Apply proposal for ${proposal.group_name}`"
                class="px-3 py-1.5 rounded-lg text-[12px] font-semibold transition-colors"
                :class="applyingGroups.has(proposal.group_id)
                  ? 'bg-emerald-100 text-emerald-400 cursor-not-allowed'
                  : 'bg-emerald-600 text-white hover:bg-emerald-700'"
              >
                {{ applyingGroups.has(proposal.group_id) ? 'Applying…' : 'Apply' }}
              </button>
              <span v-else class="text-[12px] font-semibold text-emerald-600 flex items-center gap-1">
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                Applied
              </span>
              <button
                v-if="proposal.status !== 'applied'"
                @click="dismissProposal(proposal.group_id)"
                :disabled="dismissingGroups.has(proposal.group_id)"
                :aria-label="`Dismiss proposal for ${proposal.group_name}`"
                class="px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors"
                style="color: var(--text-3);"
              >
                Dismiss
              </button>
            </div>

            <!-- Expand chevron -->
            <svg
              class="w-5 h-5 shrink-0 transition-transform duration-200"
              :class="expandedGroups.has(proposal.group_id) ? 'rotate-180' : ''"
              style="color: var(--text-3);"
              fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"
              aria-hidden="true"
            >
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </div>

          <!-- Marker table (expanded) -->
          <div v-if="expandedGroups.has(proposal.group_id)">
            <div style="border-top: 1px solid var(--border-light);">
              <!-- Empty markers -->
              <div
                v-if="proposal.proposed_markers.length === 0"
                class="px-5 py-5 text-[12px] italic"
                style="color: var(--text-3);"
              >
                No markers passed the quality gate for this group.
              </div>

              <template v-else>
                <!-- Search bar -->
                <div class="px-5 py-2.5" style="border-bottom: 1px solid var(--border-light); background: var(--surface-inset);">
                  <input
                    type="text"
                    :value="markerSearch[proposal.group_id] ?? ''"
                    @input="markerSearch[proposal.group_id] = ($event.target as HTMLInputElement).value"
                    placeholder="Search markers…"
                    aria-label="Search markers in this proposal"
                    class="w-full max-w-xs text-[12px] px-3 py-1.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400 placeholder-slate-400"
                    style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
                    @click.stop
                  />
                  <span class="ml-3 text-[11px]" style="color: var(--text-3);">
                    {{ sortedFilteredMarkers(proposal).length }} / {{ proposal.proposed_markers.length }}
                  </span>
                </div>

                <div class="overflow-y-auto" style="max-height: 360px">
                  <table class="w-full text-[12px]">
                    <thead class="sticky top-0 z-10">
                      <tr style="border-bottom: 1px solid var(--border-light); background: var(--surface-inset);">
                        <th scope="col" class="text-left px-5 py-2 w-[28%]">
                          <button @click.stop="setMarkerSort('name')" class="flex items-center gap-1 font-semibold transition-colors" style="color: var(--text-3);">
                            App
                            <span class="tabular-nums">{{ markerSortKey === 'name' ? (markerSortDir === 'asc' ? '↑' : '↓') : '' }}</span>
                          </button>
                        </th>
                        <th scope="col" class="text-left px-4 py-2 w-[22%]">
                          <button @click.stop="setMarkerSort('in_group')" class="flex items-center gap-1 font-semibold transition-colors" style="color: var(--text-3);">
                            In group
                            <span>{{ markerSortKey === 'in_group' ? (markerSortDir === 'asc' ? '↑' : '↓') : '' }}</span>
                          </button>
                        </th>
                        <th scope="col" class="text-left px-4 py-2 w-[22%]">
                          <button @click.stop="setMarkerSort('outside')" class="flex items-center gap-1 font-semibold transition-colors" style="color: var(--text-3);">
                            Outside
                            <span>{{ markerSortKey === 'outside' ? (markerSortDir === 'asc' ? '↑' : '↓') : '' }}</span>
                          </button>
                        </th>
                        <th scope="col" class="text-left px-4 py-2 w-[10%]">
                          <button @click.stop="setMarkerSort('lift')" class="flex items-center gap-1 font-semibold transition-colors" style="color: var(--text-3);">
                            Lift
                            <span>{{ markerSortKey === 'lift' ? (markerSortDir === 'asc' ? '↑' : '↓') : '' }}</span>
                          </button>
                        </th>
                        <th scope="col" class="px-4 py-2 w-[18%]"></th>
                      </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-50">
                      <tr
                        v-for="marker in sortedFilteredMarkers(proposal)"
                        :key="marker.normalized_name"
                        class="hover-surface transition-colors"
                      >
                          <!-- App name -->
                          <td class="px-5 py-2.5 font-medium truncate max-w-[240px]" style="color: var(--heading);">
                            <button
                              class="hover:text-indigo-600 hover:underline transition-colors text-left truncate"
                              @click.stop="router.push({ name: 'app-detail', params: { normalizedName: marker.normalized_name } })"
                            >{{ marker.display_name }}</button>
                          </td>

                          <!-- In-group coverage bar -->
                          <td class="px-4 py-2.5">
                            <div class="flex items-center gap-2">
                              <div class="w-20 h-1.5 rounded-full  overflow-hidden shrink-0" style="background: var(--surface-hover);">
                                <div
                                  class="h-full rounded-full bg-emerald-400"
                                  :style="{ width: `${Math.round(marker.group_coverage * 100)}%` }"
                                />
                              </div>
                              <span class="tabular-nums" style="color: var(--text-3);">
                                {{ Math.round(marker.group_coverage * 100) }}%
                                <span style="color: var(--text-3);">({{ marker.agent_count_in_group }})</span>
                              </span>
                            </div>
                          </td>

                          <!-- Outside coverage bar -->
                          <td class="px-4 py-2.5">
                            <div class="flex items-center gap-2">
                              <div class="w-20 h-1.5 rounded-full  overflow-hidden shrink-0" style="background: var(--surface-hover);">
                                <div
                                  class="h-full rounded-full bg-rose-300"
                                  :style="{ width: `${Math.round(marker.outside_coverage * 100)}%` }"
                                />
                              </div>
                              <span class="tabular-nums" style="color: var(--text-3);">
                                {{ Math.round(marker.outside_coverage * 100) }}%
                                <span style="color: var(--text-3);">({{ marker.agent_count_outside }})</span>
                              </span>
                            </div>
                          </td>

                          <!-- Lift chip -->
                          <td class="px-4 py-2.5">
                            <span
                              class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold tabular-nums"
                              :class="liftChipClass(marker.lift)"
                            >
                              {{ formatLift(marker.lift) }}
                            </span>
                          </td>

                          <!-- Actions: conflict + add button -->
                          <td class="px-4 py-2.5">
                            <div class="flex items-center justify-end gap-2">
                              <!-- Conflict indicator -->
                              <div
                                v-if="marker.shared_with_groups.length > 0"
                                class="relative group/conflict"
                              >
                                <span class="flex items-center gap-0.5 text-[11px] font-medium text-amber-500 cursor-default">
                                  <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                                    <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                                  </svg>
                                </span>
                                <div class="absolute z-10 bottom-full right-0 mb-1.5 hidden group-hover/conflict:block">
                                  <div class="bg-gray-900 text-white text-[11px] rounded-lg px-3 py-2 whitespace-nowrap shadow-lg">
                                    <p class="font-semibold mb-1 text-gray-300">Also proposed for:</p>
                                    <p v-for="gid in marker.shared_with_groups" :key="gid" class="text-gray-100">
                                      {{ groupNameMap[gid] ?? gid }}
                                    </p>
                                  </div>
                                </div>
                              </div>

                              <!-- Add single marker button -->
                              <button
                                @click.stop="addSingleMarker(proposal.group_id, marker)"
                                :disabled="addingMarkers.has(`${proposal.group_id}:${marker.normalized_name}`) || addedMarkers.has(`${proposal.group_id}:${marker.normalized_name}`)"
                                :aria-label="`Add marker ${marker.display_name}`"
                                class="text-[11px] font-medium px-2 py-0.5 rounded transition-colors"
                                :class="addedMarkers.has(`${proposal.group_id}:${marker.normalized_name}`)
                                  ? 'bg-emerald-100 text-emerald-600 cursor-default'
                                  : 'bg-indigo-50 text-indigo-600 hover:bg-indigo-100'"
                              >
                                <span v-if="addingMarkers.has(`${proposal.group_id}:${marker.normalized_name}`)">…</span>
                                <span v-else-if="addedMarkers.has(`${proposal.group_id}:${marker.normalized_name}`)">Added ✓</span>
                                <span v-else>+ Add</span>
                              </button>
                            </div>
                          </td>
                        </tr>
                    </tbody>
                  </table>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- Filtered empty state -->
        <div
          v-if="filteredProposals.length === 0 && proposals.length > 0"
          class="rounded-xl px-6 py-10 text-center text-[13px] italic"
          style="background: var(--surface); border: 1px solid var(--border); color: var(--text-3);"
        >
          No proposals match the current filter.
        </div>
      </div>

    </template>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
