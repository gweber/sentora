<!--
  AppDetailView — fleet-wide detail for a single normalised application name.

  Sections:
  1. Header — display name, publisher, risk badge, OS chips
  2. Stat bar — agent count, version count, group spread, site spread (clickable → breakdown filter)
  3. Breakdown panel — opens below stat bar on card click; chips filter the agent table
  4. Taxonomy match card (if known software)
  5. Agent table — sortable, filterable by dimension chips, exportable CSV / JSON
  6. Version distribution table — exportable
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as appsApi from '@/api/apps'
import * as libraryApi from '@/api/library'
import * as taxonomyApi from '@/api/taxonomy'
import { useAuthStore } from '@/stores/useAuthStore'
import { useToast } from '@/composables/useToast'
import type { AppAgentRow, AppDetail } from '@/types/app'
import type { LibraryEntry } from '@/types/library'

const route = useRoute()
const router = useRouter()
const toast = useToast()

// ── State ─────────────────────────────────────────────────────────────────────

const detail = ref<AppDetail | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)

// Agent table sort
type AgentCol = 'hostname' | 'group_name' | 'site_name' | 'os_type' | 'version' | 'installed_at' | 'last_active'
const agentSort = ref<AgentCol>('hostname')
const agentDir = ref<'asc' | 'desc'>('asc')
const agentSearch = ref('')

// Breakdown panel — which stat card is expanded
type BreakdownDim = 'versions' | 'groups' | 'sites'
const activeBreakdown = ref<BreakdownDim | null>(null)

// Active dimension filters — use arrays for Vue reactivity
const selectedGroups = ref<string[]>([])
const selectedSites = ref<string[]>([])
const selectedVersions = ref<string[]>([])

// ── Add to Taxonomy ──────────────────────────────────────────────────────────

const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)
const addingToTaxonomy = ref(false)
const taxonomyAdded = ref(false)
const showTaxonomyForm = ref(false)
const taxonomyCategory = ref('uncategorized')
const taxonomyCategories = ref<{ key: string; display: string }[]>([])
const librarySuggestions = ref<LibraryEntry[]>([])
const promotingLibraryId = ref<string | null>(null)

async function handleShowTaxonomyForm() {
  showTaxonomyForm.value = true
  librarySuggestions.value = []

  // Load categories and search library in parallel
  const appName = detail.value?.display_name ?? detail.value?.normalized_name ?? ''
  const [catResp, libResp] = await Promise.allSettled([
    taxonomyApi.listCategories(),
    libraryApi.listEntries({ search: appName, page_size: 5, status: 'published' }),
  ])

  if (catResp.status === 'fulfilled') {
    taxonomyCategories.value = catResp.value.categories.map((c: { key: string; display?: string }) => ({
      key: c.key,
      display: c.display ?? c.key,
    }))
  }
  if (libResp.status === 'fulfilled' && libResp.value.entries.length > 0) {
    librarySuggestions.value = libResp.value.entries
  }
}

async function handlePromoteLibraryEntry(entryId: string) {
  promotingLibraryId.value = entryId
  try {
    await libraryApi.promoteToTaxonomy(entryId, taxonomyCategory.value || undefined)
    taxonomyAdded.value = true
    showTaxonomyForm.value = false
    // Reload to pick up the new taxonomy match
    const name = route.params.normalizedName as string
    detail.value = await appsApi.getAppDetail(name)
  } catch (err) {
    toast.show(err instanceof Error ? err.message : 'Failed to promote library entry', 'error')
  } finally {
    promotingLibraryId.value = null
  }
}

async function handleAddToTaxonomy() {
  if (!detail.value) return
  addingToTaxonomy.value = true
  try {
    await taxonomyApi.addEntry({
      name: detail.value.display_name,
      patterns: [`*${detail.value.normalized_name}*`],
      publisher: detail.value.publisher ?? undefined,
      category: taxonomyCategory.value || 'uncategorized',
    })
    taxonomyAdded.value = true
    showTaxonomyForm.value = false
    // Reload to pick up the new taxonomy match
    const name = route.params.normalizedName as string
    detail.value = await appsApi.getAppDetail(name)
  } catch (err) {
    toast.show(err instanceof Error ? err.message : 'Failed to add to taxonomy', 'error')
  } finally {
    addingToTaxonomy.value = false
  }
}

// ── Load ──────────────────────────────────────────────────────────────────────

onMounted(async () => {
  const name = route.params.normalizedName as string
  try {
    detail.value = await appsApi.getAppDetail(name)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load app detail'
  } finally {
    isLoading.value = false
  }
})

// ── Breakdown data ─────────────────────────────────────────────────────────────

const groupBreakdown = computed<{ name: string; count: number }[]>(() => {
  if (!detail.value) return []
  const counts = new Map<string, number>()
  for (const a of detail.value.agents) {
    const key = a.group_name || '—'
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
})

const siteBreakdown = computed<{ name: string; count: number }[]>(() => {
  if (!detail.value) return []
  const counts = new Map<string, number>()
  for (const a of detail.value.agents) {
    const key = a.site_name || '—'
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
})

const hasActiveFilters = computed(
  () => selectedGroups.value.length > 0 || selectedSites.value.length > 0 || selectedVersions.value.length > 0,
)

// ── Interactions ───────────────────────────────────────────────────────────────

function setAgentSort(col: AgentCol) {
  if (agentSort.value === col) {
    agentDir.value = agentDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    agentSort.value = col
    agentDir.value = 'asc'
  }
}

function toggleBreakdown(dim: BreakdownDim) {
  activeBreakdown.value = activeBreakdown.value === dim ? null : dim
}

function toggleGroupFilter(name: string) {
  selectedGroups.value = selectedGroups.value.includes(name)
    ? selectedGroups.value.filter((g) => g !== name)
    : [...selectedGroups.value, name]
}

function toggleSiteFilter(name: string) {
  selectedSites.value = selectedSites.value.includes(name)
    ? selectedSites.value.filter((s) => s !== name)
    : [...selectedSites.value, name]
}

function toggleVersionFilter(ver: string) {
  selectedVersions.value = selectedVersions.value.includes(ver)
    ? selectedVersions.value.filter((v) => v !== ver)
    : [...selectedVersions.value, ver]
}

function clearAllFilters() {
  selectedGroups.value = []
  selectedSites.value = []
  selectedVersions.value = []
}

// ── Computed — filtered + sorted agent list ────────────────────────────────────

const sortedAgents = computed<AppAgentRow[]>(() => {
  if (!detail.value) return []
  let list = [...detail.value.agents]

  // Dimension filters
  if (selectedGroups.value.length > 0) {
    list = list.filter((a) => selectedGroups.value.includes(a.group_name || '—'))
  }
  if (selectedSites.value.length > 0) {
    list = list.filter((a) => selectedSites.value.includes(a.site_name || '—'))
  }
  if (selectedVersions.value.length > 0) {
    list = list.filter((a) => selectedVersions.value.includes(a.version || '—'))
  }

  // Text search
  const q = agentSearch.value.toLowerCase()
  if (q) {
    list = list.filter(
      (a) =>
        a.hostname.toLowerCase().includes(q) ||
        a.group_name.toLowerCase().includes(q) ||
        a.site_name.toLowerCase().includes(q),
    )
  }

  const dir = agentDir.value === 'asc' ? 1 : -1
  list.sort((a, b) => {
    const av = (a[agentSort.value] ?? '') as string
    const bv = (b[agentSort.value] ?? '') as string
    return dir * av.localeCompare(bv)
  })
  return list
})

const osTypes = computed<string[]>(() => {
  if (!detail.value) return []
  return [...new Set(detail.value.agents.map((a) => a.os_type).filter(Boolean))]
})

const riskColor = computed(() => {
  switch (detail.value?.risk_level?.toLowerCase()) {
    case 'critical': return 'bg-red-100 text-red-700 border-red-200'
    case 'high':     return 'bg-orange-100 text-orange-700 border-orange-200'
    case 'medium':   return 'bg-amber-100 text-amber-700 border-amber-200'
    case 'low':      return 'bg-emerald-100 text-emerald-700 border-emerald-200'
    default:         return 'badge-neutral border'
  }
})

// ── Export helpers ────────────────────────────────────────────────────────────

function exportAgentsCSV() {
  const rows = sortedAgents.value
  const headers = ['Hostname', 'Group', 'Site', 'OS', 'Version', 'Installed At', 'Last Active']
  const lines = [
    headers.join(','),
    ...rows.map((r) =>
      [
        csv(r.hostname),
        csv(r.group_name),
        csv(r.site_name),
        csv(r.os_type),
        csv(r.version ?? ''),
        csv(r.installed_at ?? ''),
        csv(r.last_active ?? ''),
      ].join(','),
    ),
  ]
  download(`${detail.value?.normalized_name ?? 'app'}-agents.csv`, lines.join('\n'), 'text/csv')
}

function exportAgentsJSON() {
  download(
    `${detail.value?.normalized_name ?? 'app'}-agents.json`,
    JSON.stringify(sortedAgents.value, null, 2),
    'application/json',
  )
}

function exportVersionsCSV() {
  if (!detail.value) return
  const lines = ['Version,Agent Count', ...detail.value.versions.map((v) => `${csv(v.version)},${v.count}`)]
  download(`${detail.value.normalized_name}-versions.csv`, lines.join('\n'), 'text/csv')
}

function exportVersionsJSON() {
  if (!detail.value) return
  download(
    `${detail.value.normalized_name}-versions.json`,
    JSON.stringify(detail.value.versions, null, 2),
    'application/json',
  )
}

function csv(val: string): string {
  if (val.includes(',') || val.includes('"') || val.includes('\n')) {
    return `"${val.replace(/"/g, '""')}"`
  }
  return val
}

function download(filename: string, content: string, mime: string) {
  const url = URL.createObjectURL(new Blob([content], { type: mime }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// ── Formatting ────────────────────────────────────────────────────────────────

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

function sortIcon(col: AgentCol): string {
  if (agentSort.value !== col) return ''
  return agentDir.value === 'asc' ? ' ↑' : ' ↓'
}
</script>

<template>
  <div class="p-6 max-w-[960px] space-y-5">

    <!-- Back link -->
    <button
      @click="router.back()"
      aria-label="Go back to previous page"
      class="flex items-center gap-1.5 text-[12px] hover:text-indigo-600 transition-colors"
      style="color: var(--text-3);"
    >
      <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
      </svg>
      Back
    </button>

    <!-- Loading -->
    <div v-if="isLoading" class="flex items-center gap-2 text-[13px]" style="color: var(--text-3);">
      <svg class="w-4 h-4 animate-spin text-indigo-400" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
      </svg>
      Loading…
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="text-[13px] rounded-xl px-5 py-4"
      style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);"
    >
      {{ error }}
    </div>

    <template v-else-if="detail">

      <!-- ── Header ── -->
      <div class="rounded-xl px-6 py-5" style="background: var(--surface); border: 1px solid var(--border);">
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <h1 class="text-[20px] font-bold leading-tight truncate" style="color: var(--heading);">
              {{ detail.display_name }}
            </h1>
            <p class="text-[12px] font-mono mt-0.5" style="color: var(--text-3);">{{ detail.normalized_name }}</p>
            <p v-if="detail.publisher" class="text-[13px] mt-1" style="color: var(--text-3);">{{ detail.publisher }}</p>
          </div>
          <div class="flex items-center gap-2 shrink-0 flex-wrap justify-end">
            <span
              v-if="detail.risk_level"
              class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-semibold border"
              :class="riskColor"
            >
              {{ detail.risk_level }}
            </span>
            <span
              v-for="os in osTypes"
              :key="os"
              class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium badge-neutral border"
            >
              {{ os }}
            </span>
            <span
              v-if="detail.taxonomy_match"
              class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200"
            >
              Known software
            </span>
            <span
              v-else
              class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200"
            >
              Unknown
            </span>
          </div>
        </div>
      </div>

      <!-- ── Stat bar ── -->
      <div class="grid grid-cols-4 gap-3">
        <!-- Agents — no breakdown, just count -->
        <div class="rounded-xl px-4 py-3.5 text-center" style="background: var(--surface); border: 1px solid var(--border);">
          <p class="text-[22px] font-bold leading-none" style="color: var(--heading);">{{ detail.agent_count }}</p>
          <p class="text-[11px] mt-1" style="color: var(--text-3);">Agents</p>
        </div>

        <!-- Versions — clickable -->
        <button
          @click="toggleBreakdown('versions')"
          class="border rounded-xl px-4 py-3.5 text-center transition-colors hover:bg-indigo-50/50"
          :class="activeBreakdown === 'versions'
            ? 'border-indigo-400 ring-1 ring-indigo-300 bg-indigo-50/60'
            : ''"
          :style="activeBreakdown === 'versions' ? '' : `background: var(--surface); border-color: var(--border);`"
        >
          <p class="text-[22px] font-bold leading-none"
            :class="activeBreakdown === 'versions' ? 'text-indigo-700' : ''"
            :style="activeBreakdown === 'versions' ? '' : `color: var(--heading);`"
          >{{ detail.versions.length }}</p>
          <p class="text-[11px] mt-1 flex items-center justify-center gap-1"
            :class="activeBreakdown === 'versions' ? 'text-indigo-500' : ''"
            :style="activeBreakdown === 'versions' ? '' : `color: var(--text-3);`"
          >
            Versions
            <svg class="w-3 h-3 transition-transform" :class="activeBreakdown === 'versions' ? 'rotate-180' : ''"
              fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </p>
        </button>

        <!-- Groups — clickable -->
        <button
          @click="toggleBreakdown('groups')"
          class="border rounded-xl px-4 py-3.5 text-center transition-colors hover:bg-indigo-50/50"
          :class="activeBreakdown === 'groups'
            ? 'border-indigo-400 ring-1 ring-indigo-300 bg-indigo-50/60'
            : ''"
          :style="activeBreakdown === 'groups' ? '' : `background: var(--surface); border-color: var(--border);`"
        >
          <p class="text-[22px] font-bold leading-none"
            :class="activeBreakdown === 'groups' ? 'text-indigo-700' : ''"
            :style="activeBreakdown === 'groups' ? '' : `color: var(--heading);`"
          >{{ detail.group_count }}</p>
          <p class="text-[11px] mt-1 flex items-center justify-center gap-1"
            :class="activeBreakdown === 'groups' ? 'text-indigo-500' : ''"
            :style="activeBreakdown === 'groups' ? '' : `color: var(--text-3);`"
          >
            Groups
            <svg class="w-3 h-3 transition-transform" :class="activeBreakdown === 'groups' ? 'rotate-180' : ''"
              fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </p>
        </button>

        <!-- Sites — clickable -->
        <button
          @click="toggleBreakdown('sites')"
          class="border rounded-xl px-4 py-3.5 text-center transition-colors hover:bg-indigo-50/50"
          :class="activeBreakdown === 'sites'
            ? 'border-indigo-400 ring-1 ring-indigo-300 bg-indigo-50/60'
            : ''"
          :style="activeBreakdown === 'sites' ? '' : `background: var(--surface); border-color: var(--border);`"
        >
          <p class="text-[22px] font-bold leading-none"
            :class="activeBreakdown === 'sites' ? 'text-indigo-700' : ''"
            :style="activeBreakdown === 'sites' ? '' : `color: var(--heading);`"
          >{{ detail.site_count }}</p>
          <p class="text-[11px] mt-1 flex items-center justify-center gap-1"
            :class="activeBreakdown === 'sites' ? 'text-indigo-500' : ''"
            :style="activeBreakdown === 'sites' ? '' : `color: var(--text-3);`"
          >
            Sites
            <svg class="w-3 h-3 transition-transform" :class="activeBreakdown === 'sites' ? 'rotate-180' : ''"
              fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </p>
        </button>
      </div>

      <!-- ── Breakdown panel ── -->
      <div
        v-if="activeBreakdown !== null"
        class="rounded-xl px-5 py-4"
        style="background: var(--surface); border: 1px solid rgb(165 180 252);"
      >
        <!-- Versions breakdown -->
        <template v-if="activeBreakdown === 'versions'">
          <div class="flex items-center justify-between mb-3">
            <p class="text-[12px] font-semibold" style="color: var(--text-2);">Filter by version</p>
            <button
              v-if="selectedVersions.length > 0"
              @click="selectedVersions = []"
              class="text-[11px] transition-colors"
              style="color: var(--text-3);"
            >Clear</button>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="v in detail.versions"
              :key="v.version"
              @click="toggleVersionFilter(v.version)"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-medium border transition-colors"
              :class="selectedVersions.includes(v.version)
                ? 'bg-indigo-600 text-white border-indigo-600'
                : ''"
              :style="selectedVersions.includes(v.version) ? '' : `background: var(--surface); color: var(--text-2); border-color: var(--border);`"
            >
              <span class="font-mono">{{ v.version }}</span>
              <span class="opacity-70">{{ v.count }}</span>
            </button>
          </div>
        </template>

        <!-- Groups breakdown -->
        <template v-else-if="activeBreakdown === 'groups'">
          <div class="flex items-center justify-between mb-3">
            <p class="text-[12px] font-semibold" style="color: var(--text-2);">Filter by group</p>
            <button
              v-if="selectedGroups.length > 0"
              @click="selectedGroups = []"
              class="text-[11px] transition-colors"
              style="color: var(--text-3);"
            >Clear</button>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="g in groupBreakdown"
              :key="g.name"
              @click="toggleGroupFilter(g.name)"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-medium border transition-colors"
              :class="selectedGroups.includes(g.name)
                ? 'bg-indigo-600 text-white border-indigo-600'
                : ''"
              :style="selectedGroups.includes(g.name) ? '' : `background: var(--surface); color: var(--text-2); border-color: var(--border);`"
            >
              {{ g.name }}
              <span class="opacity-70">{{ g.count }}</span>
            </button>
          </div>
        </template>

        <!-- Sites breakdown -->
        <template v-else-if="activeBreakdown === 'sites'">
          <div class="flex items-center justify-between mb-3">
            <p class="text-[12px] font-semibold" style="color: var(--text-2);">Filter by site</p>
            <button
              v-if="selectedSites.length > 0"
              @click="selectedSites = []"
              class="text-[11px] transition-colors"
              style="color: var(--text-3);"
            >Clear</button>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="s in siteBreakdown"
              :key="s.name"
              @click="toggleSiteFilter(s.name)"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-medium border transition-colors"
              :class="selectedSites.includes(s.name)
                ? 'bg-indigo-600 text-white border-indigo-600'
                : ''"
              :style="selectedSites.includes(s.name) ? '' : `background: var(--surface); color: var(--text-2); border-color: var(--border);`"
            >
              {{ s.name }}
              <span class="opacity-70">{{ s.count }}</span>
            </button>
          </div>
        </template>
      </div>

      <!-- ── Taxonomy match ── -->
      <div
        v-if="detail.taxonomy_match"
        class="bg-indigo-50 border border-indigo-200 rounded-xl px-5 py-4 flex items-start gap-4"
      >
        <svg class="w-5 h-5 text-indigo-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <div>
          <p class="text-[13px] font-semibold text-indigo-800">{{ detail.taxonomy_match.name }}</p>
          <p class="text-[12px] text-indigo-600 mt-0.5">
            {{ detail.taxonomy_match.category }}
            <span v-if="detail.taxonomy_match.subcategory"> · {{ detail.taxonomy_match.subcategory }}</span>
            <span v-if="detail.taxonomy_match.publisher"> · {{ detail.taxonomy_match.publisher }}</span>
            <span v-if="detail.taxonomy_match.is_universal" class="ml-2 px-1.5 py-0.5 rounded text-[10px] bg-indigo-200 text-indigo-700">Universal</span>
          </p>
        </div>
      </div>

      <!-- ── Not in taxonomy — add button ── -->
      <div
        v-else-if="isAdmin"
        class="rounded-xl px-5 py-4"
        style="background: var(--surface); border: 1px solid var(--border);"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <svg class="w-5 h-5 shrink-0 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p class="text-[13px] font-medium" style="color: var(--text-1);">Not in taxonomy</p>
              <p class="text-[11px] text-muted">This application isn't categorized yet. Add it to improve classification accuracy.</p>
            </div>
          </div>
          <button
            v-if="!showTaxonomyForm && !taxonomyAdded"
            class="shrink-0 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-[12px] font-medium hover:bg-indigo-700 transition-colors"
            @click="handleShowTaxonomyForm"
          >Add to Taxonomy</button>
          <span v-if="taxonomyAdded" class="text-[12px] font-medium text-emerald-600">Added to taxonomy</span>
        </div>

        <!-- Category picker + library suggestions (shown after clicking Add to Taxonomy) -->
        <div v-if="showTaxonomyForm" class="mt-4 space-y-3">

          <!-- Library suggestions -->
          <div v-if="librarySuggestions.length > 0">
            <p class="text-[12px] font-medium mb-2" style="color: var(--text-2);">Library matches — use existing entry:</p>
            <div class="space-y-1.5">
              <div
                v-for="lib in librarySuggestions"
                :key="lib.id"
                class="flex items-center justify-between px-3 py-2 rounded-lg"
                style="background: var(--surface-alt); border: 1px solid var(--border-light);"
              >
                <div class="min-w-0">
                  <p class="text-[13px] font-medium truncate" style="color: var(--text-1);">{{ lib.name }}</p>
                  <p class="text-[11px] text-muted">
                    {{ lib.source }} · {{ lib.markers.length }} patterns
                    <span v-if="lib.vendor"> · {{ lib.vendor }}</span>
                  </p>
                </div>
                <button
                  :disabled="promotingLibraryId === lib.id"
                  class="shrink-0 ml-3 px-2.5 py-1 rounded-md text-[11px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100 transition-colors disabled:opacity-40"
                  @click="handlePromoteLibraryEntry(lib.id)"
                >{{ promotingLibraryId === lib.id ? 'Adding...' : 'Use this' }}</button>
              </div>
            </div>
            <p class="text-[11px] text-muted mt-2">Or create manually:</p>
          </div>

          <!-- Manual add with category picker -->
          <div class="flex items-end gap-3">
            <div class="flex-1 max-w-xs">
              <label class="block text-[12px] font-medium mb-1" style="color: var(--text-2);">Category</label>
              <select
                v-model="taxonomyCategory"
                class="w-full px-3 py-1.5 rounded-lg border text-[13px] focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                style="background: var(--surface); border-color: var(--border); color: var(--text-1);"
              >
                <option value="uncategorized">Uncategorized</option>
                <option v-for="cat in taxonomyCategories" :key="cat.key" :value="cat.key">{{ cat.display }}</option>
              </select>
            </div>
            <button
              :disabled="addingToTaxonomy"
              class="px-4 py-1.5 rounded-lg bg-indigo-600 text-white text-[12px] font-medium hover:bg-indigo-700 transition-colors disabled:opacity-40"
              @click="handleAddToTaxonomy"
            >{{ addingToTaxonomy ? 'Adding...' : 'Add manually' }}</button>
            <button
              class="px-3 py-1.5 rounded-lg text-[12px] text-muted border-muted border transition-colors"
              style="background: var(--surface);"
              @click="showTaxonomyForm = false"
            >Cancel</button>
          </div>
        </div>
      </div>

      <!-- ── Agent table ── -->
      <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
        <div class="flex items-center justify-between px-5 py-3.5 gap-3 flex-wrap" style="border-bottom: 1px solid var(--border-light);">
          <div class="flex items-center gap-2 min-w-0">
            <h2 class="text-[13px] font-semibold shrink-0" style="color: var(--heading);">
              Agents
              <span class="ml-1.5 font-normal text-[12px]" style="color: var(--text-3);">{{ sortedAgents.length }} / {{ detail.agent_count }}</span>
            </h2>
            <!-- Active filter pills -->
            <div v-if="hasActiveFilters" class="flex items-center gap-1.5 flex-wrap">
              <span
                v-for="g in selectedGroups"
                :key="`g:${g}`"
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-100 text-indigo-700"
              >
                {{ g }}
                <button @click="toggleGroupFilter(g)" :aria-label="`Remove group filter: ${g}`" class="hover:text-indigo-900 leading-none">×</button>
              </span>
              <span
                v-for="s in selectedSites"
                :key="`s:${s}`"
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-violet-100 text-violet-700"
              >
                {{ s }}
                <button @click="toggleSiteFilter(s)" :aria-label="`Remove site filter: ${s}`" class="hover:text-violet-900 leading-none">×</button>
              </span>
              <span
                v-for="v in selectedVersions"
                :key="`v:${v}`"
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-teal-100 text-teal-700"
              >
                <span class="font-mono">{{ v }}</span>
                <button @click="toggleVersionFilter(v)" :aria-label="`Remove version filter: ${v}`" class="hover:text-teal-900 leading-none">×</button>
              </span>
              <button
                @click="clearAllFilters"
                class="text-[10px] underline"
                style="color: var(--text-3);"
              >Clear all</button>
            </div>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <input
              v-model="agentSearch"
              type="text"
              placeholder="Search hostname, group, site…"
              aria-label="Search agents by hostname, group, or site"
              class="text-[12px] px-3 py-1.5 rounded-lg placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 w-52"
              style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
            />
            <button
              @click="exportAgentsCSV"
              aria-label="Export agents as CSV"
              class="text-[11px] font-medium px-2.5 py-1.5 rounded-lg transition-colors"
              style="background: var(--surface); border: 1px solid var(--border); color: var(--text-2);"
            >CSV</button>
            <button
              @click="exportAgentsJSON"
              aria-label="Export agents as JSON"
              class="text-[11px] font-medium px-2.5 py-1.5 rounded-lg transition-colors"
              style="background: var(--surface); border: 1px solid var(--border); color: var(--text-2);"
            >JSON</button>
          </div>
        </div>

        <div class="overflow-y-auto" style="max-height: 420px" aria-live="polite">
          <table class="w-full text-[12px]">
            <thead class="sticky top-0 z-10 backdrop-blur-sm" style="background: var(--surface-inset); border-bottom: 1px solid var(--border-light);">
              <tr>
                <th
                  v-for="col in ([
                    { key: 'hostname',     label: 'Hostname' },
                    { key: 'group_name',   label: 'Group' },
                    { key: 'site_name',    label: 'Site' },
                    { key: 'os_type',      label: 'OS' },
                    { key: 'version',      label: 'Version' },
                    { key: 'installed_at', label: 'Installed' },
                    { key: 'last_active',  label: 'Last Active' },
                  ] as const)"
                  :key="col.key"
                  scope="col"
                  :aria-sort="agentSort === col.key ? (agentDir === 'asc' ? 'ascending' : 'descending') : 'none'"
                  class="text-left px-4 py-2 font-semibold"
                  style="color: var(--text-3);"
                >
                  <button
                    @click="setAgentSort(col.key)"
                    class="transition-colors"
                  >{{ col.label }}{{ sortIcon(col.key) }}</button>
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50">
              <tr
                v-for="agent in sortedAgents"
                :key="agent.agent_id"
                class="hover:bg-indigo-50/40 transition-colors cursor-pointer"
                @click="router.push({ name: 'agent-detail', params: { agentId: agent.agent_id } })"
              >
                <td class="px-4 py-2.5 font-medium" style="color: var(--heading);">{{ agent.hostname }}</td>
                <td class="px-4 py-2.5" style="color: var(--text-2);">
                  <router-link
                    v-if="agent.group_id"
                    :to="{ name: 'fingerprint-editor', params: { groupId: agent.group_id } }"
                    class="hover:text-indigo-600 hover:underline transition-colors no-underline"
                    style="color: inherit;"
                    @click.stop
                  >{{ agent.group_name || '—' }}</router-link>
                  <span v-else>{{ agent.group_name || '—' }}</span>
                </td>
                <td class="px-4 py-2.5" style="color: var(--text-3);">{{ agent.site_name || '—' }}</td>
                <td class="px-4 py-2.5" style="color: var(--text-3);">{{ agent.os_type || '—' }}</td>
                <td class="px-4 py-2.5 font-mono text-[11px]" style="color: var(--text-3);">{{ agent.version || '—' }}</td>
                <td class="px-4 py-2.5" style="color: var(--text-3);">{{ fmtDate(agent.installed_at) }}</td>
                <td class="px-4 py-2.5" style="color: var(--text-3);">{{ fmtDate(agent.last_active) }}</td>
              </tr>
              <tr v-if="sortedAgents.length === 0">
                <td colspan="7" class="px-4 py-6 text-center italic text-[12px]" style="color: var(--text-3);">No agents match the filters.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ── Version distribution ── -->
      <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
        <div class="flex items-center justify-between px-5 py-3.5" style="border-bottom: 1px solid var(--border-light);">
          <h2 class="text-[13px] font-semibold" style="color: var(--heading);">
            Version Distribution
            <span class="ml-1.5 font-normal text-[12px]" style="color: var(--text-3);">{{ detail.versions.length }} distinct</span>
          </h2>
          <div class="flex items-center gap-2">
            <button
              @click="exportVersionsCSV"
              aria-label="Export versions as CSV"
              class="text-[11px] font-medium px-2.5 py-1.5 rounded-lg transition-colors"
              style="background: var(--surface); border: 1px solid var(--border); color: var(--text-2);"
            >CSV</button>
            <button
              @click="exportVersionsJSON"
              aria-label="Export versions as JSON"
              class="text-[11px] font-medium px-2.5 py-1.5 rounded-lg transition-colors"
              style="background: var(--surface); border: 1px solid var(--border); color: var(--text-2);"
            >JSON</button>
          </div>
        </div>

        <div class="overflow-y-auto" style="max-height: 280px">
          <table class="w-full text-[12px]">
            <thead class="sticky top-0 z-10 backdrop-blur-sm" style="background: var(--surface-inset); border-bottom: 1px solid var(--border-light);">
              <tr>
                <th scope="col" class="text-left px-4 py-2 font-semibold" style="color: var(--text-3);">Version</th>
                <th scope="col" class="text-left px-4 py-2 font-semibold" style="color: var(--text-3);">Agents</th>
                <th scope="col" class="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50">
              <tr
                v-for="v in detail.versions"
                :key="v.version"
                class="hover-surface/60"
              >
                <td class="px-4 py-2.5 font-mono text-[11px]" style="color: var(--text-2);">{{ v.version }}</td>
                <td class="px-4 py-2.5 tabular-nums" style="color: var(--text-2);">{{ v.count }}</td>
                <td class="px-4 py-2.5 w-48">
                  <div class="h-1.5 rounded-full  overflow-hidden" style="background: var(--surface-hover);">
                    <div
                      class="h-full rounded-full bg-indigo-400"
                      :style="{ width: `${Math.round((v.count / detail!.agent_count) * 100)}%` }"
                    />
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </template>
  </div>
</template>
