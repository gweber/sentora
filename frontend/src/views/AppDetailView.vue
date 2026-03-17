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
import type { AppAgentRow, AppAgentsResponse, AppDetail, AppStats } from '@/types/app'
import type { LibraryEntry } from '@/types/library'

const route = useRoute()
const router = useRouter()
const toast = useToast()

// ── State ─────────────────────────────────────────────────────────────────────

const stats = ref<AppStats | null>(null)
const agentData = ref<AppAgentsResponse | null>(null)
const detail = computed<AppDetail | null>(() => {
  if (!stats.value) return null
  return {
    ...stats.value,
    agents: agentData.value?.agents ?? [],
    page: agentData.value?.page ?? 1,
    page_size: agentData.value?.page_size ?? 100,
    filtered_agent_count: agentData.value?.total ?? null,
  }
})
const isLoading = ref(true)
const isLoadingAgents = ref(false)
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
    // Reload stats to pick up the new taxonomy match
    const name = route.params.normalizedName as string
    stats.value = await appsApi.getAppStats(name)
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
    // Reload stats to pick up the new taxonomy match
    const name = route.params.normalizedName as string
    stats.value = await appsApi.getAppStats(name)
  } catch (err) {
    toast.show(err instanceof Error ? err.message : 'Failed to add to taxonomy', 'error')
  } finally {
    addingToTaxonomy.value = false
  }
}

// ── Load ──────────────────────────────────────────────────────────────────────

onMounted(async () => {
  isLoading.value = true
  error.value = null
  try {
    const name = route.params.normalizedName as string
    const [s, a] = await Promise.all([
      appsApi.getAppStats(name),
      appsApi.getAppAgents(name, { page: 1 }),
    ])
    stats.value = s
    agentData.value = a
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load'
  } finally {
    isLoading.value = false
  }
})

// ── Breakdown data ─────────────────────────────────────────────────────────────

// Group/site breakdowns come from the backend (full dataset, not paginated)
const groupBreakdown = computed(() => detail.value?.group_breakdown ?? [])
const siteBreakdown = computed(() => detail.value?.site_breakdown ?? [])

// ── Pagination & server-side filtering ──────────────────────────────────────
const currentPage = computed(() => agentData.value?.page ?? 1)
const effectiveAgentCount = computed(() =>
  agentData.value?.total ?? stats.value?.agent_count ?? 0,
)
const totalPages = computed(() => {
  const ps = agentData.value?.page_size ?? 100
  return Math.max(1, Math.ceil(effectiveAgentCount.value / ps))
})

async function fetchAgents(page = 1) {
  isLoadingAgents.value = true
  try {
    const name = route.params.normalizedName as string
    agentData.value = await appsApi.getAppAgents(name, {
      page,
      pageSize: agentData.value?.page_size ?? 100,
      groupNames: selectedGroups.value.length ? selectedGroups.value : undefined,
      siteNames: selectedSites.value.length ? selectedSites.value : undefined,
      versions: selectedVersions.value.length ? selectedVersions.value : undefined,
      search: agentSearch.value || undefined,
    })
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load agents'
  } finally {
    isLoadingAgents.value = false
  }
}

function goToPage(p: number) {
  if (p < 1 || p > totalPages.value) return
  fetchAgents(p)
}

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
  fetchAgents(1)
}

function toggleSiteFilter(name: string) {
  selectedSites.value = selectedSites.value.includes(name)
    ? selectedSites.value.filter((s) => s !== name)
    : [...selectedSites.value, name]
  fetchAgents(1)
}

function toggleVersionFilter(ver: string) {
  selectedVersions.value = selectedVersions.value.includes(ver)
    ? selectedVersions.value.filter((v) => v !== ver)
    : [...selectedVersions.value, ver]
  fetchAgents(1)
}

function clearAllFilters() {
  selectedGroups.value = []
  selectedSites.value = []
  selectedVersions.value = []
  agentSearch.value = ''
  fetchAgents(1)
}

// ── Computed — filtered + sorted agent list ────────────────────────────────────

// Agent list comes pre-filtered and paginated from the API.
// Local sort is applied for column header clicks within the current page.
const sortedAgents = computed<AppAgentRow[]>(() => {
  if (!detail.value) return []
  const list = [...detail.value.agents]
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
    case 'critical': return 'bg-[var(--error-bg)] text-[var(--error-text)] border-[var(--error-border)]'
    case 'high':     return 'bg-[var(--warn-bg)] text-[var(--warn-text)] border-[var(--warn-border)]'
    case 'medium':   return 'bg-[var(--warn-bg)] text-[var(--warn-text)] border-[var(--warn-border)]'
    case 'low':      return 'bg-[var(--success-bg)] text-[var(--success-text)] border-[var(--success-border)]'
    default:         return 'badge-neutral border'
  }
})

// ── Export helpers ────────────────────────────────────────────────────────────

async function exportAgents(format: 'csv' | 'json') {
  if (!detail.value) return
  const name = detail.value.normalized_name
  const params = new URLSearchParams()
  params.set('format', format)
  for (const g of selectedGroups.value) params.append('group_name', g)
  for (const s of selectedSites.value) params.append('site_name', s)
  for (const v of selectedVersions.value) params.append('version', v)
  if (agentSearch.value) params.set('search', agentSearch.value)

  try {
    const { default: client } = await import('@/api/client')
    const resp = await client.get(
      `/apps/export/${encodeURIComponent(name)}?${params.toString()}`,
      { responseType: 'blob' },
    )
    const blob = new Blob([resp.data])
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${name}-agents.${format}`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (e) {
    toast.show(e instanceof Error ? e.message : 'Export failed', 'error')
  }
}

function exportAgentsCSV() { exportAgents('csv') }
function exportAgentsJSON() { exportAgents('json') }

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
      class="flex items-center gap-1.5 text-[12px] hover:text-[var(--info-text)] transition-colors"
      style="color: var(--text-3);"
    >
      <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
      </svg>
      Back
    </button>

    <!-- Loading -->
    <div v-if="isLoading" class="flex items-center gap-2 text-[13px]" style="color: var(--text-3);">
      <svg class="w-4 h-4 animate-spin text-[var(--brand-primary)]" fill="none" viewBox="0 0 24 24">
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
              class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium bg-[var(--info-bg)] text-[var(--info-text)] border border-[var(--border)]"
            >
              Known software
            </span>
            <span
              v-else
              class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium bg-[var(--warn-bg)] text-[var(--warn-text)] border border-[var(--warn-border)]"
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
          class="border rounded-xl px-4 py-3.5 text-center transition-colors hover:bg-[var(--surface-hover)]"
          :class="activeBreakdown === 'versions'
            ? 'border-[var(--brand-primary)] ring-1 ring-[var(--brand-primary-light)] bg-[var(--info-bg)]'
            : ''"
          :style="activeBreakdown === 'versions' ? '' : `background: var(--surface); border-color: var(--border);`"
        >
          <p class="text-[22px] font-bold leading-none"
            :class="activeBreakdown === 'versions' ? 'text-[var(--info-text)]' : ''"
            :style="activeBreakdown === 'versions' ? '' : `color: var(--heading);`"
          >{{ detail.versions.length }}</p>
          <p class="text-[11px] mt-1 flex items-center justify-center gap-1"
            :class="activeBreakdown === 'versions' ? 'text-[var(--brand-primary)]' : ''"
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
          class="border rounded-xl px-4 py-3.5 text-center transition-colors hover:bg-[var(--surface-hover)]"
          :class="activeBreakdown === 'groups'
            ? 'border-[var(--brand-primary)] ring-1 ring-[var(--brand-primary-light)] bg-[var(--info-bg)]'
            : ''"
          :style="activeBreakdown === 'groups' ? '' : `background: var(--surface); border-color: var(--border);`"
        >
          <p class="text-[22px] font-bold leading-none"
            :class="activeBreakdown === 'groups' ? 'text-[var(--info-text)]' : ''"
            :style="activeBreakdown === 'groups' ? '' : `color: var(--heading);`"
          >{{ detail.group_count }}</p>
          <p class="text-[11px] mt-1 flex items-center justify-center gap-1"
            :class="activeBreakdown === 'groups' ? 'text-[var(--brand-primary)]' : ''"
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
          class="border rounded-xl px-4 py-3.5 text-center transition-colors hover:bg-[var(--surface-hover)]"
          :class="activeBreakdown === 'sites'
            ? 'border-[var(--brand-primary)] ring-1 ring-[var(--brand-primary-light)] bg-[var(--info-bg)]'
            : ''"
          :style="activeBreakdown === 'sites' ? '' : `background: var(--surface); border-color: var(--border);`"
        >
          <p class="text-[22px] font-bold leading-none"
            :class="activeBreakdown === 'sites' ? 'text-[var(--info-text)]' : ''"
            :style="activeBreakdown === 'sites' ? '' : `color: var(--heading);`"
          >{{ detail.site_count }}</p>
          <p class="text-[11px] mt-1 flex items-center justify-center gap-1"
            :class="activeBreakdown === 'sites' ? 'text-[var(--brand-primary)]' : ''"
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
                ? 'bg-[var(--brand-primary)] text-white border-[var(--brand-primary)]'
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
                ? 'bg-[var(--brand-primary)] text-white border-[var(--brand-primary)]'
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
                ? 'bg-[var(--brand-primary)] text-white border-[var(--brand-primary)]'
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
        class="bg-[var(--info-bg)] border border-[var(--border)] rounded-xl px-5 py-4 flex items-start gap-4"
      >
        <svg class="w-5 h-5 text-[var(--brand-primary)] shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <div>
          <p class="text-[13px] font-semibold text-[var(--heading)]">{{ detail.taxonomy_match.name }}</p>
          <p class="text-[12px] text-[var(--info-text)] mt-0.5">
            {{ detail.taxonomy_match.category }}
            <span v-if="detail.taxonomy_match.subcategory"> · {{ detail.taxonomy_match.subcategory }}</span>
            <span v-if="detail.taxonomy_match.publisher"> · {{ detail.taxonomy_match.publisher }}</span>
            <span v-if="detail.taxonomy_match.is_universal" class="ml-2 px-1.5 py-0.5 rounded text-[10px] bg-[var(--info-bg)] text-[var(--info-text)]">Universal</span>
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
            class="shrink-0 px-3 py-1.5 rounded-lg bg-[var(--brand-primary)] text-white text-[12px] font-medium hover:opacity-90 transition-colors"
            @click="handleShowTaxonomyForm"
          >Add to Taxonomy</button>
          <span v-if="taxonomyAdded" class="text-[12px] font-medium text-[var(--success-text)]">Added to taxonomy</span>
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
                  class="shrink-0 ml-3 px-2.5 py-1 rounded-md text-[11px] font-medium bg-[var(--info-bg)] text-[var(--info-text)] border border-[var(--border)] hover:bg-[var(--surface-hover)] transition-colors disabled:opacity-40"
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
                class="w-full px-3 py-1.5 rounded-lg border text-[13px] focus:outline-none focus:ring-2 focus:ring-[var(--input-focus)]"
                style="background: var(--surface); border-color: var(--border); color: var(--text-1);"
              >
                <option value="uncategorized">Uncategorized</option>
                <option v-for="cat in taxonomyCategories" :key="cat.key" :value="cat.key">{{ cat.display }}</option>
              </select>
            </div>
            <button
              :disabled="addingToTaxonomy"
              class="px-4 py-1.5 rounded-lg bg-[var(--brand-primary)] text-white text-[12px] font-medium hover:opacity-90 transition-colors disabled:opacity-40"
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

      <!-- ── EOL Lifecycle ── -->
      <div
        v-if="detail.eol"
        class="rounded-xl px-5 py-4"
        :style="`background: var(--surface); border: 1px solid ${detail.eol.versions.some(v => v.is_eol) ? 'var(--error-border)' : detail.eol.versions.some(v => v.is_security_only) ? 'var(--warn-border)' : 'var(--border)'};`"
      >
        <div class="flex items-start gap-3 mb-3">
          <svg class="w-5 h-5 shrink-0 mt-0.5 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-0.5">
              <h3 class="text-[14px] font-semibold" style="color: var(--heading);">EOL Lifecycle</h3>
              <a
                :href="`https://endoflife.date/${detail.eol.eol_product_id}`"
                target="_blank"
                rel="noopener"
                class="text-[11px] text-[var(--info-text)] hover:underline"
              >endoflife.date/{{ detail.eol.eol_product_id }}</a>
            </div>
            <p class="text-[12px]" style="color: var(--text-3);">
              Tracked as <span class="font-medium" style="color: var(--text-2);">{{ detail.eol.product_name }}</span>
              via {{ detail.eol.match_source }} match ({{ Math.round(detail.eol.match_confidence * 100) }}%)
            </p>
          </div>
        </div>
        <!-- Per-version EOL status table -->
        <div v-if="detail.eol.versions.length > 0" class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead style="border-bottom: 1px solid var(--border-light);">
              <tr>
                <th class="text-left px-3 py-2 font-semibold" style="color: var(--text-3);">Version</th>
                <th class="text-left px-3 py-2 font-semibold" style="color: var(--text-3);">Agents</th>
                <th class="text-left px-3 py-2 font-semibold" style="color: var(--text-3);">Cycle</th>
                <th class="text-left px-3 py-2 font-semibold" style="color: var(--text-3);">Status</th>
                <th class="text-left px-3 py-2 font-semibold" style="color: var(--text-3);">EOL Date</th>
              </tr>
            </thead>
            <tbody class="divide-y" style="border-color: var(--border-light);">
              <tr v-for="v in detail.eol.versions" :key="v.version">
                <td class="px-3 py-2 font-mono tabular-nums" style="color: var(--text-2);">{{ v.version }}</td>
                <td class="px-3 py-2 tabular-nums" style="color: var(--text-3);">{{ v.agent_count }}</td>
                <td class="px-3 py-2" style="color: var(--text-3);">{{ v.cycle || '—' }}</td>
                <td class="px-3 py-2">
                  <span
                    v-if="v.is_eol"
                    class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-[var(--error-bg)] text-[var(--error-text)] border border-[var(--error-border)]"
                  >EOL</span>
                  <span
                    v-else-if="v.is_security_only"
                    class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-[var(--warn-bg)] text-[var(--warn-text)] border border-[var(--warn-border)]"
                  >Security Only</span>
                  <span
                    v-else-if="v.cycle"
                    class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-[var(--success-bg)] text-[var(--success-text)] border border-[var(--success-border)]"
                  >Supported</span>
                  <span
                    v-else
                    class="text-[10px]" style="color: var(--text-3);"
                  >Unknown</span>
                </td>
                <td class="px-3 py-2" style="color: var(--text-3);">
                  {{ v.eol_date || (v.support_end ? `Support ends ${v.support_end}` : '—') }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ── Agent table ── -->
      <div class="rounded-xl overflow-hidden relative" style="background: var(--surface); border: 1px solid var(--border);">
        <!-- Subtle loading overlay for agent-only refreshes -->
        <div v-if="isLoadingAgents" class="absolute inset-0 z-10 flex items-center justify-center" style="background: rgba(var(--brand-primary-rgb), 0.03);"></div>
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
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-[var(--scope-account-bg)] text-[var(--scope-account-text)]"
              >
                {{ g }}
                <button @click="toggleGroupFilter(g)" :aria-label="`Remove group filter: ${g}`" class="hover:text-[var(--info-text)] leading-none">×</button>
              </span>
              <span
                v-for="s in selectedSites"
                :key="`s:${s}`"
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-[var(--scope-site-bg)] text-[var(--scope-site-text)]"
              >
                {{ s }}
                <button @click="toggleSiteFilter(s)" :aria-label="`Remove site filter: ${s}`" class="hover:text-[var(--scope-site-text)] leading-none">×</button>
              </span>
              <span
                v-for="v in selectedVersions"
                :key="`v:${v}`"
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-[var(--scope-group-bg)] text-[var(--scope-group-text)]"
              >
                <span class="font-mono">{{ v }}</span>
                <button @click="toggleVersionFilter(v)" :aria-label="`Remove version filter: ${v}`" class="hover:text-[var(--scope-group-text)] leading-none">×</button>
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
              class="text-[12px] px-3 py-1.5 rounded-lg placeholder-[var(--text-3)] focus:outline-none focus:ring-1 focus:ring-[var(--input-focus)] w-52"
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
                class="hover:bg-[var(--surface-hover)] transition-colors cursor-pointer"
                @click="router.push({ name: 'agent-detail', params: { agentId: agent.agent_id } })"
              >
                <td class="px-4 py-2.5 font-medium" style="color: var(--heading);">{{ agent.hostname }}</td>
                <td class="px-4 py-2.5" style="color: var(--text-2);">
                  <router-link
                    v-if="agent.group_id"
                    :to="{ name: 'fingerprint-editor', params: { groupId: agent.group_id } }"
                    class="hover:text-[var(--info-text)] hover:underline transition-colors no-underline"
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

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-between px-5 py-3" style="border-top: 1px solid var(--border-light);">
          <span class="text-[11px]" style="color: var(--text-3);">
            Page {{ currentPage }} of {{ totalPages }}
            ({{ effectiveAgentCount }} {{ detail.filtered_agent_count != null ? 'matching' : 'total' }} agents{{ detail.filtered_agent_count != null ? ` of ${detail.agent_count}` : '' }})
          </span>
          <div class="flex items-center gap-1">
            <button
              class="px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors"
              :style="currentPage <= 1 ? 'color: var(--text-3); cursor: default;' : 'color: var(--info-text);'"
              :disabled="currentPage <= 1"
              @click="goToPage(currentPage - 1)"
            >Prev</button>
            <button
              v-for="p in Math.min(totalPages, 7)" :key="p"
              class="w-7 h-7 rounded-md text-[11px] font-medium transition-colors"
              :style="p === currentPage ? 'background: var(--brand-primary); color: white;' : 'color: var(--text-2);'"
              @click="goToPage(p)"
            >{{ p }}</button>
            <span v-if="totalPages > 7" class="text-[11px]" style="color: var(--text-3);">...</span>
            <button
              class="px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors"
              :style="currentPage >= totalPages ? 'color: var(--text-3); cursor: default;' : 'color: var(--info-text);'"
              :disabled="currentPage >= totalPages"
              @click="goToPage(currentPage + 1)"
            >Next</button>
          </div>
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
                      class="h-full rounded-full bg-[var(--brand-primary)]"
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
