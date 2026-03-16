<!--
  Classification view — trigger runs, browse all results, export.

  Layout:
  ┌─ Header: stats cards + Run button ─────────────────────────────┐
  ├─ Filter bar: verdict pills, search input, group filter, export ─┤
  └─ Results table with pagination ────────────────────────────────┘
-->
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useClassificationStore } from '@/stores/useClassificationStore'
import type { ClassificationVerdict } from '@/types/classification'
import { formatRelativeTime } from '@/utils/formatters'

const store = useClassificationStore()

// ── Filters ───────────────────────────────────────────────────────────────────

const filterVerdict = ref<ClassificationVerdict | ''>('')
const filterSearch = ref('')
const currentPage = ref(1)
const PAGE_SIZE = 50

let _searchDebounce: ReturnType<typeof setTimeout> | null = null

function applyVerdict(v: ClassificationVerdict | '') {
  filterVerdict.value = v
  currentPage.value = 1
  load()
}

function onSearchInput() {
  if (_searchDebounce) clearTimeout(_searchDebounce)
  _searchDebounce = setTimeout(() => {
    currentPage.value = 1
    load()
  }, 300)
}

async function load() {
  try {
    await store.fetchResults({
      page: currentPage.value,
      limit: PAGE_SIZE,
      classification: filterVerdict.value || undefined,
      search: filterSearch.value.trim() || undefined,
    })
  } catch {
    // Error is tracked in store.error
  }
}

function goPage(p: number) {
  currentPage.value = p
  load()
}

const totalPages = computed(() => Math.max(1, Math.ceil(store.resultsTotal / PAGE_SIZE)))
const pageNumbers = computed(() => {
  const pages: (number | '…')[] = []
  const tp = totalPages.value
  if (tp <= 7) {
    for (let i = 1; i <= tp; i++) pages.push(i)
  } else {
    pages.push(1)
    if (currentPage.value > 3) pages.push('…')
    for (let i = Math.max(2, currentPage.value - 1); i <= Math.min(tp - 1, currentPage.value + 1); i++) pages.push(i)
    if (currentPage.value < tp - 2) pages.push('…')
    pages.push(tp)
  }
  return pages
})

// ── Run classification ────────────────────────────────────────────────────────

async function runClassification() {
  await store.triggerClassification()
}

// Auto-reload results when run completes (isRunning flips false)
watch(() => store.isRunning, (running, was) => {
  if (was && !running) load()
})

// ── Export ────────────────────────────────────────────────────────────────────

function doExport(fmt: 'csv' | 'json') {
  store.exportResults(fmt, {
    classification: filterVerdict.value || undefined,
    search: filterSearch.value.trim() || undefined,
  })
}

// ── Verdict helpers ───────────────────────────────────────────────────────────

const VERDICTS = ['correct', 'misclassified', 'ambiguous', 'unclassifiable'] as const

const verdictStyle: Record<string, string> = {
  correct:        'bg-[var(--success-bg)] text-[var(--success-text)]',
  misclassified:  'bg-[var(--warn-bg)] text-[var(--warn-text)]',
  ambiguous:      'bg-[var(--warn-bg)] text-[var(--warn-text)]',
  unclassifiable: 'badge-neutral',
}

function verdictCount(v: ClassificationVerdict): number {
  return store.overview?.[v] ?? 0
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(async () => {
  await store.fetchOverview()
  load()
})

onUnmounted(() => {
  store.stopPolling()
  if (_searchDebounce) clearTimeout(_searchDebounce)
})
</script>

<template>
  <div class="p-6 space-y-5">

    <!-- ── Overview cards + trigger ──────────────────────────────────────── -->
    <div class="flex flex-wrap items-start gap-4">

      <!-- Stat cards -->
      <div class="flex flex-wrap gap-3 flex-1 min-w-0">
        <div
          v-for="v in VERDICTS"
          :key="v"
          class="flex flex-col gap-1 rounded-xl px-4 py-3 min-w-[120px]"
          style="background: var(--surface); border: 1px solid var(--border);"
        >
          <span class="text-[11px] font-semibold uppercase tracking-widest capitalize" style="color: var(--text-3);">{{ v }}</span>
          <span class="text-[22px] font-bold leading-none" style="color: var(--heading);">{{ verdictCount(v as ClassificationVerdict) }}</span>
        </div>
        <div class="flex flex-col gap-1 rounded-xl px-4 py-3 min-w-[120px]" style="background: var(--surface); border: 1px solid var(--border);">
          <span class="text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Total</span>
          <span class="text-[22px] font-bold leading-none" style="color: var(--heading);">{{ store.overview?.total ?? '—' }}</span>
        </div>
      </div>

      <!-- Run button + status -->
      <div class="flex flex-col items-end gap-2 shrink-0">
        <button
          class="flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-semibold transition-colors"
          :class="store.isRunning
            ? 'bg-[var(--info-bg)] text-[var(--brand-primary-light)] cursor-not-allowed border border-[var(--brand-primary-light)]'
            : 'bg-[var(--brand-primary)] text-white hover:bg-[var(--brand-primary-dark)]'"
          :disabled="store.isRunning"
          aria-label="Run Classification"
          @click="runClassification"
        >
          <svg
            class="w-4 h-4"
            :class="store.isRunning ? 'animate-spin' : ''"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {{ store.isRunning ? 'Running…' : 'Run Classification' }}
        </button>
        <span v-if="store.overview?.last_computed_at" class="text-[11px]" style="color: var(--text-3);">
          Last run {{ formatRelativeTime(store.overview.last_computed_at) }}
        </span>
        <span v-if="store.error" class="text-[11px] text-[var(--error-text)] max-w-[240px] text-right">{{ store.error }}</span>
      </div>
    </div>

    <!-- ── Filter bar ─────────────────────────────────────────────────────── -->
    <div class="flex flex-wrap items-center gap-2">

      <!-- Verdict pills -->
      <button
        class="px-3 py-1.5 rounded-md text-[12px] font-medium transition-colors"
        :class="filterVerdict === ''
          ? 'bg-[var(--brand-primary)] text-white'
          : ''"
        :style="filterVerdict === '' ? '' : `background: var(--surface); border: 1px solid var(--border); color: var(--text-2);`"
        :aria-pressed="filterVerdict === ''"
        @click="applyVerdict('')"
      >All</button>
      <button
        v-for="v in VERDICTS"
        :key="v"
        class="px-3 py-1.5 rounded-md text-[12px] font-medium transition-colors capitalize"
        :class="filterVerdict === v
          ? 'bg-[var(--brand-primary)] text-white'
          : ''"
        :style="filterVerdict === v ? '' : `background: var(--surface); border: 1px solid var(--border); color: var(--text-2);`"
        :aria-pressed="filterVerdict === v"
        @click="applyVerdict(v)"
      >{{ v }}</button>

      <!-- Search -->
      <div class="relative ml-auto">
        <svg class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style="color: var(--text-3);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          v-model="filterSearch"
          type="text"
          placeholder="Search hostname…"
          aria-label="Search classification results by hostname"
          class="pl-8 pr-3 py-1.5 text-[12px] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary-light)] w-44"
          style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
          @input="onSearchInput"
        />
      </div>

      <!-- Export -->
      <div class="flex gap-1.5 ml-1">
        <button
          class="px-3 py-1.5 rounded-md text-[12px] font-medium transition-colors"
          style="background: var(--surface); border: 1px solid var(--border); color: var(--text-2);"
          aria-label="Export results as CSV"
          @click="doExport('csv')"
        >↓ CSV</button>
        <button
          class="px-3 py-1.5 rounded-md text-[12px] font-medium transition-colors"
          style="background: var(--surface); border: 1px solid var(--border); color: var(--text-2);"
          aria-label="Export results as JSON"
          @click="doExport('json')"
        >↓ JSON</button>
      </div>
    </div>

    <!-- ── Loading ────────────────────────────────────────────────────────── -->
    <div v-if="store.isLoading && store.results.length === 0" class="flex items-center justify-center py-20 text-[13px]" style="color: var(--text-3);">
      Loading…
    </div>

    <!-- ── Empty state ────────────────────────────────────────────────────── -->
    <div
      v-else-if="!store.isLoading && store.results.length === 0"
      class="flex flex-col items-center justify-center py-20"
      style="color: var(--text-3);"
    >
      <svg class="w-10 h-10 mb-3 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <p class="text-[14px] font-medium" style="color: var(--text-3);">No results yet</p>
      <p class="text-[12px] mt-1">Configure fingerprints and click "Run Classification" to get started.</p>
    </div>

    <!-- ── Results table ──────────────────────────────────────────────────── -->
    <div v-else class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);" aria-live="polite">
      <table class="w-full border-collapse">
        <thead>
          <tr style="background: var(--surface-inset); border-bottom: 1px solid var(--border);">
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Hostname</th>
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Group</th>
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Verdict</th>
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Suggested</th>
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Top Score</th>
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Computed</th>
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="result in store.results"
            :key="result.agent_id"
            class="last:border-0 transition-colors"
            style="border-bottom: 1px solid var(--border-light);"
            :class="{ 'opacity-40': result.acknowledged }"
          >
            <td class="px-4 py-3">
              <router-link
                :to="`/agents/${result.agent_id}`"
                class="text-[13px] font-medium text-[var(--brand-primary)] hover:text-[var(--brand-primary-dark)] no-underline"
              >
                {{ result.hostname }}
              </router-link>
              <!-- Anomaly flag -->
              <span
                v-if="result.anomaly_flag"
                class="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[var(--error-bg)] text-[var(--error-text)]"
                :title="`Anomaly score: ${result.anomaly_score?.toFixed(3) ?? 'n/a'}`"
              >⚠</span>
            </td>
            <td class="px-4 py-3 text-[13px]" style="color: var(--text-2);">{{ result.current_group_name }}</td>
            <td class="px-4 py-3">
              <span
                class="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold capitalize"
                :class="verdictStyle[result.classification] ?? ' text-muted'" style="background: var(--surface-hover);"
              >{{ result.classification }}</span>
            </td>
            <td class="px-4 py-3 text-[13px]" style="color: var(--text-3);">{{ result.suggested_group_name ?? '—' }}</td>
            <td class="px-4 py-3 text-[13px] font-mono" style="color: var(--text-2);">
              {{ result.match_scores?.[0]?.score != null ? result.match_scores[0].score.toFixed(3) : '—' }}
            </td>
            <td class="px-4 py-3 text-[12px]" style="color: var(--text-3);">{{ formatRelativeTime(result.computed_at) }}</td>
            <td class="px-4 py-3">
              <button
                v-if="!result.acknowledged"
                class="px-3 py-1 rounded text-[12px] transition-colors"
                style="border: 1px solid var(--border); color: var(--text-2);"
                :aria-label="`Acknowledge ${result.hostname}`"
                @click="store.acknowledgeAnomaly(result.agent_id)"
              >Acknowledge</button>
              <span v-else class="text-[12px] font-medium text-[var(--success-text)]">Reviewed</span>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="flex items-center justify-between px-4 py-3" style="border-top: 1px solid var(--border); background: var(--surface-inset);">
        <span class="text-[12px]" style="color: var(--text-3);">
          {{ store.resultsTotal }} result{{ store.resultsTotal === 1 ? '' : 's' }} · page {{ currentPage }} of {{ totalPages }}
        </span>
        <div class="flex gap-1">
          <button
            class="px-2.5 py-1 rounded text-[12px] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            style="border: 1px solid var(--border); color: var(--text-2);"
            :disabled="currentPage === 1"
            aria-label="Previous page"
            @click="goPage(currentPage - 1)"
          >‹</button>
          <template v-for="(p, i) in pageNumbers" :key="i">
            <button
              v-if="p !== '…'"
              class="px-2.5 py-1 rounded text-[12px] transition-colors"
              :class="p === currentPage
                ? 'bg-[var(--brand-primary)] text-white border-[var(--brand-primary)]'
                : ''"
              :style="p === currentPage ? 'border: 1px solid rgb(79 70 229);' : `border: 1px solid var(--border); color: var(--text-2);`"
              :aria-label="`Page ${p}`"
              :aria-current="p === currentPage ? 'page' : undefined"
              @click="goPage(p as number)"
            >{{ p }}</button>
            <span v-else class="px-1.5 py-1 text-[12px]" style="color: var(--text-3);">…</span>
          </template>
          <button
            class="px-2.5 py-1 rounded text-[12px] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            style="border: 1px solid var(--border); color: var(--text-2);"
            :disabled="currentPage === totalPages"
            aria-label="Next page"
            @click="goPage(currentPage + 1)"
          >›</button>
        </div>
      </div>
    </div>

  </div>
</template>
