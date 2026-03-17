<!--
  Fingerprint Editor — three-panel layout.
  Left: Taxonomy catalog + suggestions  |  Center: Marker drop zone  |  Right: Pattern preview
-->
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useFingerprintStore } from '@/stores/useFingerprintStore'
import { useTaxonomyStore } from '@/stores/useTaxonomyStore'
import type { SoftwareEntry } from '@/types/taxonomy'
import type { FingerprintMarker } from '@/types/fingerprint'
import * as fingerprintApi from '@/api/fingerprints'
import * as taxonomyApi from '@/api/taxonomy'
import type { PatternPreviewResponse } from '@/types/taxonomy'

const route = useRoute()
const fpStore = useFingerprintStore()
const taxStore = useTaxonomyStore()

const groupId = computed(() => (route.params.groupId as string) || '')
const expandedCategory = ref<string | null>(null)
const isDragOver = ref(false)
const selectedMarkerId = ref<string | null>(null)
const patternPreview = ref<PatternPreviewResponse | null>(null)
const isLoadingPreview = ref(false)
const pendingWeights = ref<Record<string, number>>({})
const catalogSearch = ref('')
const isComputing = ref(false)

onMounted(async () => {
  await taxStore.fetchCategories()
  if (groupId.value) {
    await fpStore.ensureFingerprint(groupId.value)
    await fpStore.loadSuggestions(groupId.value)
  }
})

watch(
  () => groupId.value,
  async (id) => {
    if (id) {
      expandedCategory.value = null
      selectedMarkerId.value = null
      patternPreview.value = null
      pendingWeights.value = {}
      await fpStore.ensureFingerprint(id)
      await fpStore.loadSuggestions(id)
    }
  },
)

// ── Catalog ───────────────────────────────────────────────────────────────────

const filteredCategories = computed(() => {
  if (!catalogSearch.value.trim()) return taxStore.categories
  const q = catalogSearch.value.toLowerCase()
  return taxStore.categories.filter((c) => c.display.toLowerCase().includes(q))
})

async function toggleCategory(key: string) {
  if (expandedCategory.value === key) {
    expandedCategory.value = null
    return
  }
  expandedCategory.value = key
  await taxStore.fetchEntriesByCategory(key)
}

function onDragStart(e: DragEvent, entry: SoftwareEntry) {
  const pattern = entry.patterns[0] ?? entry.name.toLowerCase().replace(/\s+/g, '_')
  e.dataTransfer?.setData(
    'application/json',
    JSON.stringify({ pattern, display_name: entry.name, category: entry.category }),
  )
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'copy'
}

// ── Drop zone ─────────────────────────────────────────────────────────────────

function onDragOver(e: DragEvent) {
  e.preventDefault()
  isDragOver.value = true
}

function onDragLeave(e: DragEvent) {
  const t = e.currentTarget as HTMLElement
  if (!t.contains(e.relatedTarget as Node)) isDragOver.value = false
}

async function onDrop(e: DragEvent) {
  e.preventDefault()
  isDragOver.value = false
  const raw = e.dataTransfer?.getData('application/json')
  if (!raw) return
  try {
    const p = JSON.parse(raw) as { pattern: string; display_name: string; category: string }
    await addMarkerPayload(p)
  } catch {
    /* ignore malformed drag data */
  }
}

async function addMarkerPayload(p: {
  pattern: string
  display_name: string
  category: string
}) {
  if (!groupId.value) return
  await fpStore.ensureFingerprint(groupId.value)
  await fpStore.addMarker({
    pattern: p.pattern,
    display_name: p.display_name,
    category: p.category,
    weight: 1.0,
    source: 'manual',
  })
}

async function addEntryAsMarker(entry: SoftwareEntry) {
  await addMarkerPayload({
    pattern: entry.patterns[0] ?? entry.name.toLowerCase().replace(/\s+/g, '_'),
    display_name: entry.name,
    category: entry.category,
  })
}

// ── Marker management ─────────────────────────────────────────────────────────

const markers = computed(() => fpStore.activeFingerprint?.markers ?? [])
const hasMarkers = computed(() => markers.value.length > 0)

async function removeMarker(id: string) {
  if (selectedMarkerId.value === id) {
    selectedMarkerId.value = null
    patternPreview.value = null
  }
  await fpStore.removeMarker(id)
}

async function selectMarker(marker: FingerprintMarker) {
  if (selectedMarkerId.value === marker.id) {
    selectedMarkerId.value = null
    patternPreview.value = null
    return
  }
  selectedMarkerId.value = marker.id
  isLoadingPreview.value = true
  patternPreview.value = null
  try {
    patternPreview.value = await taxonomyApi.previewPattern({
      pattern: marker.pattern,
    })
  } catch {
    patternPreview.value = null
  } finally {
    isLoadingPreview.value = false
  }
}

function getDisplayWeight(marker: FingerprintMarker): number {
  return pendingWeights.value[marker.id] ?? marker.weight
}

function onWeightInput(markerId: string, e: Event) {
  const val = parseFloat((e.target as HTMLInputElement).value)
  pendingWeights.value = { ...pendingWeights.value, [markerId]: val }
}

async function commitWeight(marker: FingerprintMarker) {
  const w = pendingWeights.value[marker.id]
  if (w === undefined) return
  await fpStore.updateMarker(marker.id, { weight: Math.max(0.1, Math.min(2.0, w)) })
  const copy = { ...pendingWeights.value }
  delete copy[marker.id]
  pendingWeights.value = copy
}

function weightLabel(w: number): string {
  if (w >= 1.8) return 'Critical'
  if (w >= 1.2) return 'High'
  if (w >= 0.8) return 'Medium'
  return 'Low'
}

function weightColor(w: number): string {
  if (w >= 1.8) return 'text-[var(--error-text)]'
  if (w >= 1.2) return 'text-[var(--warn-text)]'
  if (w >= 0.8) return 'text-[var(--info-text)]'
  return 'text-[var(--text-3)]'
}

function sourceColor(source: string): string {
  return source === 'statistical'
    ? 'bg-[var(--accent-bg)] text-[var(--accent-text)]'
    : source === 'seed'
      ? 'bg-[var(--success-bg)] text-[var(--success-text)]'
      : 'bg-[var(--info-bg)] text-[var(--info-text)]'
}

// ── Suggestions ───────────────────────────────────────────────────────────────

const pendingSuggestions = computed(() =>
  fpStore.suggestions.filter((s) => s.status === 'pending'),
)

// Modal state
const showSuggestionsModal = ref(false)
const suggestionSearch = ref('')
const suggestionSort = ref<'score' | 'group_coverage' | 'outside_coverage' | 'display_name'>('score')
const suggestionSortDir = ref<'desc' | 'asc'>('desc')

const filteredSortedSuggestions = computed(() => {
  let list = pendingSuggestions.value
  const q = suggestionSearch.value.trim().toLowerCase()
  if (q) list = list.filter((s) => s.display_name.toLowerCase().includes(q))
  return [...list].sort((a, b) => {
    const av = a[suggestionSort.value] as number | string
    const bv = b[suggestionSort.value] as number | string
    if (typeof av === 'string') {
      return suggestionSortDir.value === 'asc'
        ? av.localeCompare(bv as string)
        : (bv as string).localeCompare(av)
    }
    return suggestionSortDir.value === 'asc'
      ? (av as number) - (bv as number)
      : (bv as number) - (av as number)
  })
})

function toggleSort(col: typeof suggestionSort.value) {
  if (suggestionSort.value === col) {
    suggestionSortDir.value = suggestionSortDir.value === 'desc' ? 'asc' : 'desc'
  } else {
    suggestionSort.value = col
    suggestionSortDir.value = col === 'display_name' ? 'asc' : 'desc'
  }
}

function sortIcon(col: typeof suggestionSort.value): string {
  if (suggestionSort.value !== col) return '↕'
  return suggestionSortDir.value === 'desc' ? '↓' : '↑'
}

async function computeSuggestions() {
  if (!groupId.value || isComputing.value) return
  isComputing.value = true
  suggestionSearch.value = ''
  try {
    fpStore.suggestions = await fingerprintApi.computeSuggestions(groupId.value)
    showSuggestionsModal.value = true
  } catch {
    /* silently handle — no data pre-sync */
  } finally {
    isComputing.value = false
  }
}

async function acceptSuggestion(id: string) {
  if (!groupId.value) return
  await fpStore.acceptSuggestion(id)
}

async function rejectSuggestion(id: string) {
  if (!groupId.value) return
  await fpStore.rejectSuggestion(id)
}

async function acceptSuggestionKeepOpen(id: string) {
  await acceptSuggestion(id)
  // keep modal open so user can continue reviewing
}


// ── Stats ─────────────────────────────────────────────────────────────────────

const selectedMarker = computed(
  () => markers.value.find((m) => m.id === selectedMarkerId.value) ?? null,
)

// ── Import / Export ──────────────────────────────────────────────────────────

const isExporting = ref(false)
const isImporting = ref(false)
const importResult = ref<{ imported: number; skipped: number; errors: string[] } | null>(null)
let importResultTimeout: ReturnType<typeof setTimeout> | null = null

onUnmounted(() => {
  if (importResultTimeout) clearTimeout(importResultTimeout)
})

async function handleExport() {
  isExporting.value = true
  try {
    await fingerprintApi.exportFingerprints()
  } catch {
    /* silently fail */
  } finally {
    isExporting.value = false
  }
}

function triggerImportDialog() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json,application/json'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    isImporting.value = true
    importResult.value = null
    try {
      const text = await file.text()
      const items = JSON.parse(text)
      importResult.value = await fingerprintApi.importFingerprints(items, 'merge')
      // Reload current fingerprint if any
      if (groupId.value) {
        await fpStore.ensureFingerprint(groupId.value)
      }
      if (importResultTimeout) clearTimeout(importResultTimeout)
      importResultTimeout = setTimeout(() => { importResult.value = null }, 5000)
    } catch {
      importResult.value = { imported: 0, skipped: 0, errors: ['Invalid JSON file'] }
      if (importResultTimeout) clearTimeout(importResultTimeout)
      importResultTimeout = setTimeout(() => { importResult.value = null }, 5000)
    } finally {
      isImporting.value = false
    }
  }
  input.click()
}
</script>

<template>
  <div class="flex flex-col h-full overflow-hidden">

    <!-- ── Group name header (when a group is active) ──────────────────────── -->
    <div
      v-if="groupId && fpStore.activeFingerprint"
      class="shrink-0 flex items-center gap-3 px-6 py-3"
      style="background: var(--surface); border-bottom: 1px solid var(--border);"
    >
      <div class="flex items-center justify-center w-7 h-7 rounded-lg bg-[var(--info-bg)]0/10 shrink-0">
        <svg class="w-[15px] h-[15px] text-[var(--brand-primary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
        </svg>
      </div>
      <div class="min-w-0">
        <p class="text-[11px] leading-none mb-1 truncate" style="color: var(--text-3);">
          <span v-if="fpStore.activeFingerprint.account_name">{{ fpStore.activeFingerprint.account_name }}</span>
          <span v-if="fpStore.activeFingerprint.account_name && fpStore.activeFingerprint.site_name" class="mx-1 opacity-50">›</span>
          <span v-if="fpStore.activeFingerprint.site_name">{{ fpStore.activeFingerprint.site_name }}</span>
        </p>
        <p class="text-[15px] font-semibold leading-none truncate" style="color: var(--heading);">
          {{ fpStore.activeFingerprint.group_name || groupId }}
        </p>
      </div>
      <div class="ml-auto flex items-center gap-2">
        <!-- Import result toast -->
        <span v-if="importResult" class="text-[11px] font-medium" :class="importResult.errors.length > 0 ? 'text-[var(--error-text)]' : 'text-[var(--success-text)]'">
          {{ importResult.errors.length > 0 ? importResult.errors[0] : `Imported ${importResult.imported}, skipped ${importResult.skipped}` }}
        </span>

        <span v-if="hasMarkers" class="text-[12px]" style="color: var(--text-3);">
          {{ markers.length }} marker{{ markers.length !== 1 ? 's' : '' }}
        </span>

        <!-- Export -->
        <button
          class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors"
          style="background: var(--surface); border: 1px solid var(--border); color: var(--text-2);"
          :disabled="isExporting"
          aria-label="Export fingerprints"
          @click="handleExport"
        >
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          {{ isExporting ? 'Exporting…' : 'Export' }}
        </button>

        <!-- Import -->
        <button
          class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors"
          style="background: var(--surface); border: 1px solid var(--border); color: var(--text-2);"
          :disabled="isImporting"
          aria-label="Import fingerprints"
          @click="triggerImportDialog"
        >
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
          {{ isImporting ? 'Importing…' : 'Import' }}
        </button>
      </div>
    </div>

    <!-- ── Content row ─────────────────────────────────────────────────────── -->
    <div class="flex flex-1 overflow-hidden">

    <!-- ── Empty state: no group selected ──────────────────────────────────── -->
    <div
      v-if="!groupId"
      class="flex flex-col items-center justify-center flex-1 gap-5"
      style="color: var(--text-3);"
    >
      <div class="w-16 h-16 rounded-2xl flex items-center justify-center" style="background: var(--surface-inset);">
        <svg class="w-8 h-8" style="color: var(--text-3);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round"
            d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
        </svg>
      </div>
      <div class="text-center">
        <p class="text-[15px] font-semibold mb-1" style="color: var(--text-2);">No group selected</p>
        <p class="text-[13px]" style="color: var(--text-3);">Choose a group from the Groups page to build its fingerprint.</p>
      </div>
      <router-link
        to="/groups"
        class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--brand-primary)] text-white text-[13px] font-medium hover:opacity-90 transition-colors no-underline"
      >
        Browse Groups
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M17 8l4 4m0 0l-4 4m4-4H3" />
        </svg>
      </router-link>
    </div>

    <!-- ── Three-panel layout ──────────────────────────────────────────────── -->
    <template v-else>

      <!-- ── Left: Taxonomy catalog ─────────────────────────────────────────── -->
      <div class="w-[230px] shrink-0 flex flex-col overflow-hidden" style="border-right: 1px solid var(--border); background: var(--surface-alt);">

        <!-- Catalog header + search -->
        <div class="px-3 py-3 shrink-0 space-y-2" style="border-bottom: 1px solid var(--border);">
          <p class="text-[10px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Catalog</p>
          <input
            v-model="catalogSearch"
            type="text"
            placeholder="Search categories…"
            aria-label="Search taxonomy categories"
            class="w-full text-[12px] px-2.5 py-1.5 rounded-md focus:outline-none focus:ring-1 placeholder:text-[var(--text-3)]"
            style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
          />
        </div>

        <!-- Category list -->
        <div class="flex-1 overflow-y-auto">
          <div v-for="cat in filteredCategories" :key="cat.key">
            <!-- Category row -->
            <button
              class="w-full flex items-center justify-between px-3 py-2 transition-colors text-left"
              style="color: var(--text-2);"
              @click="toggleCategory(cat.key)"
            >
              <div class="flex items-center gap-2 min-w-0">
                <svg
                  class="w-3 h-3 shrink-0 transition-transform"
                  :class="expandedCategory === cat.key ? 'rotate-90' : ''"
                  style="color: var(--text-3);"
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
                </svg>
                <span class="text-[12px] font-medium truncate" style="color: var(--text-2);">{{ cat.display }}</span>
              </div>
              <span class="ml-1 shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded-full" style="background: var(--badge-bg); color: var(--badge-text);">
                {{ cat.entry_count }}
              </span>
            </button>

            <!-- Category entries (expanded) -->
            <div v-if="expandedCategory === cat.key" style="background: var(--surface); border-bottom: 1px solid var(--border-light);">
              <div
                v-if="taxStore.isLoading && !taxStore.entriesByCategory[cat.key]"
                class="px-6 py-2 text-[11px] italic"
                style="color: var(--text-3);"
              >
                Loading…
              </div>
              <div
                v-for="entry in taxStore.entriesByCategory[cat.key] ?? []"
                :key="entry.id"
                draggable="true"
                @dragstart="onDragStart($event, entry)"
                class="group flex items-center justify-between px-4 pl-8 py-1.5 hover:bg-[var(--info-bg)] cursor-grab transition-colors"
              >
                <span class="text-[11px] truncate flex-1 min-w-0" style="color: var(--text-2);">{{ entry.name }}</span>
                <button
                  class="ml-2 shrink-0 opacity-0 group-hover:opacity-100 focus:opacity-100 w-5 h-5 flex items-center justify-center rounded bg-[var(--info-bg)] hover:bg-[var(--brand-primary)] text-[var(--info-text)] hover:text-white transition-all text-[14px] leading-none"
                  title="Add as marker"
                  :aria-label="`Add ${entry.name} as marker`"
                  @click.stop="addEntryAsMarker(entry)"
                >
                  +
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Suggestions trigger bar -->
        <div class="shrink-0 px-3 py-2.5" style="border-top: 1px solid var(--border);">
          <button
            class="w-full flex items-center justify-between px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-colors border"
            :class="isComputing
              ? 'bg-[var(--accent-bg)] text-violet-400 border-[var(--accent-muted)] cursor-not-allowed'
              : 'bg-[var(--accent-bg)] text-[var(--accent-text)] hover:bg-[var(--accent-bg)] border-[var(--accent-muted)]'"
            :disabled="isComputing"
            @click="computeSuggestions"
          >
            <span>{{ isComputing ? 'Computing…' : 'Suggestions' }}</span>
            <span v-if="isComputing" class="animate-spin text-[10px]">⟳</span>
            <span v-else-if="pendingSuggestions.length > 0" class="font-bold text-[var(--accent-text)]">{{ pendingSuggestions.length }}</span>
            <span v-else class="text-[10px]" style="color: var(--text-3);">click to compute</span>
          </button>
        </div>
      </div>

      <!-- ── Suggestions modal ──────────────────────────────────────────────── -->
      <Teleport to="body">
        <div
          v-if="showSuggestionsModal"
          class="fixed inset-0 z-50 flex items-center justify-center p-4"
          style="background: rgba(15,20,36,0.5)"
          @click.self="showSuggestionsModal = false"
        >
          <div
            class="rounded-2xl shadow-2xl flex flex-col overflow-hidden"
            style="background: var(--surface); width: 800px; height: 70vh; min-width: 480px; min-height: 320px; max-width: 95vw; max-height: 90vh; resize: both;"
            role="dialog"
            aria-modal="true"
            aria-label="Fingerprint suggestions"
          >

            <!-- Modal header -->
            <div class="flex items-center justify-between px-5 py-4 shrink-0" style="border-bottom: 1px solid var(--border);">
              <div>
                <p class="text-[15px] font-semibold" style="color: var(--heading);">
                  Suggestions
                  <span v-if="pendingSuggestions.length > 0" class="ml-1.5 text-[13px] font-bold text-[var(--accent-text)]">{{ pendingSuggestions.length }}</span>
                </p>
                <p class="text-[12px] mt-0.5" style="color: var(--text-3);">TF-IDF ranked apps that distinguish this group — accept to add as markers.</p>
              </div>
              <button
                class="w-7 h-7 flex items-center justify-center rounded-lg transition-colors text-[18px] leading-none"
                style="color: var(--text-3);"
                aria-label="Close suggestions dialog"
                @click="showSuggestionsModal = false"
              >×</button>
            </div>

            <!-- Search + count -->
            <div class="px-5 py-3 shrink-0 flex items-center gap-3" style="border-bottom: 1px solid var(--border-light);">
              <div class="relative flex-1">
                <svg class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style="color: var(--text-3);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  v-model="suggestionSearch"
                  type="text"
                  placeholder="Filter by name…"
                  aria-label="Filter suggestions by name"
                  class="w-full pl-8 pr-3 py-1.5 text-[12px] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary-light)]"
                  style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
                  autofocus
                />
              </div>
              <span class="text-[12px] shrink-0" style="color: var(--text-3);">{{ filteredSortedSuggestions.length }} shown</span>
            </div>

            <!-- Table -->
            <div class="overflow-y-auto flex-1">
              <table class="w-full border-collapse">
                <thead class="sticky top-0 z-10" style="background: var(--surface-inset); border-bottom: 1px solid var(--border);">
                  <tr>
                    <th scope="col" class="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-widest w-[35%]" style="color: var(--text-3);">
                      <div class="flex items-center gap-1.5">
                        <button class="flex items-center gap-1 transition-colors" @click="toggleSort('display_name')">
                          Name <span class="font-mono text-[10px]">{{ sortIcon('display_name') }}</span>
                        </button>
                      </div>
                    </th>
                    <th scope="col" class="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">
                      <div class="flex items-center gap-1.5">
                        <button class="flex items-center gap-1 transition-colors" @click="toggleSort('score')">
                          Lift <span class="font-mono text-[10px]">{{ sortIcon('score') }}</span>
                        </button>
                        <span class="col-tip" data-tip="Lift: agents in this group are N× more likely to have this app than a random fleet agent. Higher = more distinctive." aria-label="Lift: agents in this group are N times more likely to have this app than a random fleet agent. Higher is more distinctive.">ⓘ</span>
                      </div>
                    </th>
                    <th scope="col" class="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">
                      <div class="flex items-center gap-1.5">
                        <button class="flex items-center gap-1 transition-colors" @click="toggleSort('group_coverage')">
                          In Group <span class="font-mono text-[10px]">{{ sortIcon('group_coverage') }}</span>
                        </button>
                        <span class="col-tip" data-tip="% of agents in this group that have the app installed. High coverage = reliable marker." aria-label="Percentage of agents in this group that have the app installed. High coverage means reliable marker.">ⓘ</span>
                      </div>
                    </th>
                    <th scope="col" class="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">
                      <div class="flex items-center gap-1.5">
                        <button class="flex items-center gap-1 transition-colors" @click="toggleSort('outside_coverage')">
                          Outside <span class="font-mono text-[10px]">{{ sortIcon('outside_coverage') }}</span>
                        </button>
                        <span class="col-tip" data-tip="% of agents outside this group that also have the app. Low outside coverage = better discriminator." aria-label="Percentage of agents outside this group that also have the app. Low outside coverage means better discriminator.">ⓘ</span>
                      </div>
                    </th>
                    <th scope="col" class="px-4 py-2.5 text-right text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="s in filteredSortedSuggestions"
                    :key="s.id"
                    class="last:border-0 hover:bg-[var(--accent-bg)]/50 transition-colors group"
                    style="border-bottom: 1px solid var(--border-light);"
                  >
                    <td class="px-4 py-3">
                      <p class="text-[13px] font-medium" style="color: var(--heading);">{{ s.display_name }}</p>
                      <code class="text-[10px] font-mono" style="color: var(--text-3);">{{ s.normalized_name }}</code>
                    </td>
                    <td class="px-4 py-3">
                      <span
                        class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold tabular-nums"
                        :class="s.score >= 10 ? 'bg-[var(--scope-site-bg)] text-[var(--scope-site-text)] border border-[var(--border)]'
                              : s.score >= 5  ? 'bg-[var(--info-bg)] text-[var(--info-text)] border border-[var(--border)]'
                              : ' text-muted border-muted border'" style="background: var(--surface-hover);"
                      >
                        {{ s.score >= 99 ? '>99×' : Number.isInteger(s.score) ? `${s.score}×` : `${s.score.toFixed(1)}×` }}
                      </span>
                    </td>
                    <td class="px-4 py-3">
                      <div class="flex items-center gap-2">
                        <div class="w-20  rounded-full h-1.5" style="background: var(--surface-hover);">
                          <div class="bg-[var(--accent-bg)]0 h-1.5 rounded-full" :style="`width: ${Math.round(s.group_coverage * 100)}%`"></div>
                        </div>
                        <span class="text-[12px]" style="color: var(--text-2);">{{ Math.round(s.group_coverage * 100) }}%</span>
                        <span class="text-[11px]" style="color: var(--text-3);">({{ s.agent_count_in_group }})</span>
                      </div>
                    </td>
                    <td class="px-4 py-3">
                      <div class="flex items-center gap-2">
                        <div class="w-20  rounded-full h-1.5" style="background: var(--surface-hover);">
                          <div class="bg-[var(--status-warn-text)] h-1.5 rounded-full" :style="`width: ${Math.round(s.outside_coverage * 100)}%`"></div>
                        </div>
                        <span class="text-[12px]" style="color: var(--text-2);">{{ Math.round(s.outside_coverage * 100) }}%</span>
                        <span class="text-[11px]" style="color: var(--text-3);">({{ s.agent_count_outside }})</span>
                      </div>
                    </td>
                    <td class="px-4 py-3">
                      <div class="flex items-center justify-end gap-1.5">
                        <button
                          class="px-2.5 py-1 rounded-md text-[11px] font-medium bg-[var(--brand-primary)] text-white hover:opacity-90 transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"
                          :aria-label="`Accept suggestion ${s.display_name}`"
                          @click="acceptSuggestionKeepOpen(s.id)"
                        >Accept</button>
                        <button
                          class="px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"
                          style="background: var(--surface); border: 1px solid var(--border); color: var(--text-3);"
                          :aria-label="`Reject suggestion ${s.display_name}`"
                          @click="rejectSuggestion(s.id)"
                        >Reject</button>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="filteredSortedSuggestions.length === 0">
                    <td colspan="5" class="px-4 py-10 text-center text-[13px] italic" style="color: var(--text-3);">No suggestions match your filter.</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Modal footer -->
            <div class="px-5 py-3 shrink-0 flex items-center justify-between" style="border-top: 1px solid var(--border); background: var(--surface-inset);">
              <span class="text-[12px]" style="color: var(--text-3);">Accepted suggestions become markers in the Fingerprint Definition.</span>
              <button
                class="px-4 py-1.5 rounded-lg text-[12px] font-medium transition-colors"
                style="background: var(--badge-bg); color: var(--text-2);"
                @click="showSuggestionsModal = false"
              >Close</button>
            </div>
          </div>
        </div>
      </Teleport>

      <!-- ── Center: Fingerprint definition ─────────────────────────────────── -->
      <div class="flex-1 flex flex-col overflow-hidden min-w-0" style="border-right: 1px solid var(--border);">

        <!-- Header -->
        <div class="px-5 py-3 shrink-0 flex items-center justify-between" style="border-bottom: 1px solid var(--border);">
          <p class="text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">
            Fingerprint Definition
          </p>
        </div>

        <!-- Drop zone / marker list -->
        <div
          class="flex-1 overflow-y-auto p-5 transition-colors"
          :class="isDragOver ? 'bg-[var(--info-bg)]' : ''"
          @dragover="onDragOver"
          @dragleave="onDragLeave"
          @drop="onDrop"
        >
          <!-- Empty state / drop hint -->
          <div
            v-if="!hasMarkers"
            class="flex flex-col items-center justify-center h-full border-2 border-dashed rounded-xl gap-3 transition-colors"
            :class="isDragOver ? 'border-[var(--brand-primary)] bg-[var(--info-bg)] text-[var(--brand-primary)]' : 'text-[var(--text-3)]'"
            :style="!isDragOver ? 'border-color: var(--border);' : ''"
          >
            <svg class="w-10 h-10 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            <p class="text-[13px] font-medium">Drag entries from the catalog</p>
            <p class="text-[12px] opacity-70">or click the + button on any entry</p>
          </div>

          <!-- Marker list -->
          <div v-else class="space-y-2">
            <div
              v-for="marker in markers"
              :key="marker.id"
              class="rounded-lg transition-all cursor-pointer group"
              :class="
                selectedMarkerId === marker.id
                  ? 'border-[var(--border)] bg-[var(--info-bg)] shadow-sm'
                  : 'hover:border-[var(--border)] hover:shadow-sm'
              "
              :style="selectedMarkerId === marker.id
                ? 'border: 1px solid rgb(165 180 252);'
                : `background: var(--surface); border: 1px solid var(--border);`"
              @click="selectMarker(marker)"
            >
              <!-- Marker header row -->
              <div class="flex items-center gap-3 px-4 py-3">
                <!-- Drag handle -->
                <svg
                  class="w-4 h-4 shrink-0 cursor-grab"
                  style="color: var(--text-3);"
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"
                >
                  <path stroke-linecap="round" stroke-linejoin="round"
                    d="M4 8h16M4 16h16" />
                </svg>

                <!-- Name + source badge -->
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2 min-w-0">
                    <span class="text-[13px] font-medium truncate" style="color: var(--heading);">{{ marker.display_name }}</span>
                    <span
                      class="shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded-full"
                      :class="sourceColor(marker.source)"
                    >{{ marker.source }}</span>
                  </div>
                  <code class="text-[11px] font-mono" style="color: var(--text-3);">{{ marker.pattern }}</code>
                </div>

                <!-- Weight indicator -->
                <div class="shrink-0 text-right">
                  <span class="text-[12px] font-semibold" :class="weightColor(getDisplayWeight(marker))">
                    {{ getDisplayWeight(marker).toFixed(1) }}
                  </span>
                  <p class="text-[10px]" style="color: var(--text-3);">{{ weightLabel(getDisplayWeight(marker)) }}</p>
                </div>

                <!-- Delete button -->
                <button
                  class="shrink-0 w-6 h-6 flex items-center justify-center rounded text-[var(--text-3)] hover:text-[var(--error-text)] hover:bg-[var(--error-bg)] transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"
                  title="Remove marker"
                  :aria-label="`Remove marker ${marker.display_name}`"
                  @click.stop="removeMarker(marker.id)"
                >
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <!-- Weight slider (expanded when selected) -->
              <div
                v-if="selectedMarkerId === marker.id"
                class="px-4 pb-3 border-t border-[var(--border-light)]"
                @click.stop
              >
                <div class="flex items-center gap-3 pt-2">
                  <span class="text-[11px] shrink-0 w-14" style="color: var(--text-3);">Weight</span>
                  <input
                    type="range"
                    min="0.1"
                    max="2.0"
                    step="0.1"
                    :value="getDisplayWeight(marker)"
                    class="flex-1 accent-indigo-600"
                    @input="onWeightInput(marker.id, $event)"
                    @change="commitWeight(marker)"
                  />
                  <span class="text-[12px] font-semibold text-[var(--info-text)] w-8 text-right shrink-0">
                    {{ getDisplayWeight(marker).toFixed(1) }}
                  </span>
                </div>
              </div>
            </div>

            <!-- Drop hint while dragging over existing markers -->
            <div
              v-if="isDragOver"
              class="flex items-center justify-center h-12 rounded-lg border-2 border-dashed border-[var(--border)] text-[var(--brand-primary)] text-[12px] font-medium"
            >
              Drop to add marker
            </div>
          </div>
        </div>
      </div>

      <!-- ── Right: Pattern preview ──────────────────────────────────────────── -->
      <div class="w-[260px] shrink-0 flex flex-col overflow-hidden" style="background: var(--surface-alt);">

        <!-- Header -->
        <div class="px-4 py-3 shrink-0" style="border-bottom: 1px solid var(--border);">
          <p class="text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Pattern Preview</p>
        </div>

        <!-- No marker selected -->
        <div
          v-if="!selectedMarkerId"
          class="flex flex-col items-center justify-center flex-1 gap-3 p-4 text-center"
          style="color: var(--text-3);"
        >
          <svg class="w-8 h-8 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <p class="text-[12px]">Click a marker to see which agents match its pattern</p>
        </div>

        <!-- Loading preview -->
        <div
          v-else-if="isLoadingPreview"
          class="flex flex-col items-center justify-center flex-1 gap-2"
          style="color: var(--text-3);"
        >
          <svg class="w-5 h-5 animate-spin text-[var(--brand-primary)]" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <p class="text-[12px]">Searching…</p>
        </div>

        <!-- Preview results -->
        <div v-else class="flex flex-col overflow-hidden flex-1">

          <!-- Selected marker info -->
          <div v-if="selectedMarker" class="px-4 py-3 shrink-0" style="border-bottom: 1px solid var(--border); background: var(--surface);">
            <code class="text-[12px] font-mono text-[var(--info-text)] block truncate">{{ selectedMarker.pattern }}</code>
            <div class="mt-1.5 flex items-center gap-2">
              <span
                class="text-[11px] font-semibold px-2 py-0.5 rounded-full"
                :class="
                  patternPreview && patternPreview.total_apps > 0
                    ? 'bg-[var(--success-bg)] text-[var(--success-text)]'
                    : ' text-muted'
                " style="background: var(--surface-hover);"
              >
                {{ patternPreview?.total_apps ?? 0 }} apps
              </span>
              <span
                class="text-[11px] font-semibold px-2 py-0.5 rounded-full"
                :class="
                  patternPreview && patternPreview.total_agents > 0
                    ? 'bg-[var(--info-bg)] text-[var(--info-text)]'
                    : ' text-muted'
                " style="background: var(--surface-hover);"
              >
                {{ patternPreview?.total_agents ?? 0 }} agents
              </span>
            </div>
          </div>

          <!-- No preview data (pre-sync) -->
          <div
            v-if="!patternPreview || patternPreview.app_matches.length === 0"
            class="flex flex-col items-center justify-center flex-1 gap-2 p-4 text-center"
            style="color: var(--text-3);"
          >
            <p class="text-[12px]">
              {{ patternPreview ? 'No apps matched this pattern.' : 'Run a sync to see live matches.' }}
            </p>
          </div>

          <!-- App match list -->
          <div v-else class="flex-1 overflow-y-auto">
            <div
              v-for="app in patternPreview.app_matches"
              :key="app.normalized_name"
              class="px-4 py-2.5 transition-colors"
              style="border-bottom: 1px solid var(--border-light);"
            >
              <p class="text-[12px] font-medium truncate" style="color: var(--heading);">{{ app.display_name }}</p>
              <div class="flex items-center justify-between mt-0.5">
                <p class="text-[11px] truncate" style="color: var(--text-3);">{{ app.publisher || 'Unknown publisher' }}</p>
                <span class="shrink-0 text-[10px] font-medium" style="color: var(--text-3);">{{ app.agent_count }} agents</span>
              </div>
            </div>

            <!-- Group breakdown -->
            <div v-if="patternPreview.group_counts.length > 0" class="px-4 py-3" style="border-top: 1px solid var(--border); background: var(--surface-inset);">
              <p class="text-[10px] font-semibold uppercase tracking-widest mb-2" style="color: var(--text-3);">By Group</p>
              <div class="space-y-1">
                <div
                  v-for="gc in patternPreview.group_counts"
                  :key="gc.group_name"
                  class="flex items-center justify-between"
                >
                  <span class="text-[11px] truncate" style="color: var(--text-2);">{{ gc.group_name }}</span>
                  <span class="shrink-0 text-[10px] font-medium" style="color: var(--text-3);">{{ gc.agent_count }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

    </template>
    </div><!-- end content row -->
  </div>
</template>

<style scoped>
/* Column header info tooltip */
.col-tip {
  position: relative;
  font-size: 11px;
  color: #94a3b8;
  cursor: default;
  user-select: none;
  font-style: normal;
  text-transform: none;
  letter-spacing: 0;
  font-weight: 400;
}

.col-tip::after {
  content: attr(data-tip);
  position: absolute;
  top: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  width: 220px;
  padding: 6px 9px;
  background: #1e293b;
  color: #e2e8f0;
  font-size: 11px;
  line-height: 1.5;
  border-radius: 6px;
  white-space: normal;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s;
  z-index: 100;
  box-shadow: 0 4px 12px rgba(0,0,0,0.25);
}

.col-tip:hover::after {
  opacity: 1;
}
</style>
