<!--
  AppsOverviewView — fleet-wide application inventory.

  Features:
  - Paginated table of all distinct normalised apps with agent counts
  - Search, sort by name or agent count
  - Taxonomy category badge per row
  - Filter: all / known / unknown
  - "Add to taxonomy" action per row (opens modal with pre-filled pattern)
  - Click row → App Detail page
  - CSV / JSON export of current view
-->
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as appsApi from '@/api/apps'
import * as taxonomyApi from '@/api/taxonomy'
import type { AppListItem } from '@/types/app'
import type { CategorySummary, SoftwareEntryCreateRequest } from '@/types/taxonomy'

const router = useRouter()

// ── State ─────────────────────────────────────────────────────────────────────

const apps = ref<AppListItem[]>([])
const total = ref(0)
const knownTotal = ref<number | null>(null)
const unknownTotal = ref<number | null>(null)
const page = ref(1)
const limit = ref(100)
const isLoading = ref(true)
const error = ref<string | null>(null)

// Filters
const search = ref('')
const sortField = ref<'agent_count' | 'name'>('agent_count')
const sortOrder = ref<'asc' | 'desc'>('desc')
const taxonomyFilter = ref<'all' | 'known' | 'unknown'>('all')

// Add-to-taxonomy modal
const showTaxModal = ref(false)
const taxSaving = ref(false)
const taxCategories = ref<CategorySummary[]>([])
const taxTarget = ref<AppListItem | null>(null)
const taxError = ref<string | null>(null)
const taxForm = ref({
  name: '',
  patterns: '',
  category: '',
  category_display: '',
  publisher: '',
})

// ── Data loading ──────────────────────────────────────────────────────────────

let searchTimeout: ReturnType<typeof setTimeout> | null = null

async function load() {
  isLoading.value = true
  error.value = null
  try {
    const res = await appsApi.listApps({
      q: search.value,
      sort: sortField.value,
      order: sortOrder.value,
      page: page.value,
      limit: limit.value,
    })
    apps.value = res.apps
    total.value = res.total
    if (res.known_count != null) knownTotal.value = res.known_count
    if (res.unknown_count != null) unknownTotal.value = res.unknown_count
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load applications'
  } finally {
    isLoading.value = false
  }
}

onMounted(load)

watch(search, () => {
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    page.value = 1
    load()
  }, 300)
})

watch([sortField, sortOrder], () => {
  page.value = 1
  load()
})

watch(page, load)

onUnmounted(() => {
  if (searchTimeout) clearTimeout(searchTimeout)
})

// ── Computed ──────────────────────────────────────────────────────────────────

const filteredApps = computed(() => {
  if (taxonomyFilter.value === 'all') return apps.value
  if (taxonomyFilter.value === 'known') return apps.value.filter((a) => a.category !== null)
  return apps.value.filter((a) => a.category === null)
})

const totalPages = computed(() => Math.ceil(total.value / limit.value))

const statKnown = computed(() => apps.value.filter((a) => a.category !== null).length)
const statUnknown = computed(() => apps.value.filter((a) => a.category === null).length)

// ── Sorting ───────────────────────────────────────────────────────────────────

function toggleSort(field: 'agent_count' | 'name') {
  if (sortField.value === field) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortOrder.value = field === 'agent_count' ? 'desc' : 'asc'
  }
}

function sortIcon(field: string): string {
  if (sortField.value !== field) return ''
  return sortOrder.value === 'asc' ? ' ↑' : ' ↓'
}

// ── Add to taxonomy ───────────────────────────────────────────────────────────

async function openTaxModal(app: AppListItem) {
  taxTarget.value = app
  taxForm.value = {
    name: app.display_name,
    patterns: app.normalized_name,
    category: '',
    category_display: '',
    publisher: app.publisher ?? '',
  }

  // Load categories if not loaded
  if (taxCategories.value.length === 0) {
    try {
      const res = await taxonomyApi.listCategories()
      taxCategories.value = res.categories
    } catch {
      // proceed without categories — user can type a new one
    }
  }

  showTaxModal.value = true
}

function selectCategory(cat: CategorySummary) {
  taxForm.value.category = cat.key
  taxForm.value.category_display = cat.display
}

async function saveTaxEntry() {
  taxSaving.value = true
  taxError.value = null
  try {
    const payload: SoftwareEntryCreateRequest = {
      name: taxForm.value.name.trim(),
      patterns: taxForm.value.patterns
        .split('\n')
        .map((p) => p.trim())
        .filter(Boolean),
      category: taxForm.value.category.trim(),
      category_display: taxForm.value.category_display.trim() || taxForm.value.category.trim(),
      publisher: taxForm.value.publisher.trim() || null,
    }
    await taxonomyApi.addEntry(payload)
    showTaxModal.value = false

    // Refresh to show updated taxonomy status
    await load()
  } catch (e) {
    taxError.value = e instanceof Error ? e.message : 'Failed to save taxonomy entry'
  } finally {
    taxSaving.value = false
  }
}

// ── Export ─────────────────────────────────────────────────────────────────────

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

function exportCSV() {
  const rows = filteredApps.value
  const headers = ['Normalized Name', 'Display Name', 'Publisher', 'Agent Count', 'Category']
  const lines = [
    headers.join(','),
    ...rows.map((r) =>
      [
        csv(r.normalized_name),
        csv(r.display_name),
        csv(r.publisher ?? ''),
        String(r.agent_count),
        csv(r.category_display ?? r.category ?? ''),
      ].join(','),
    ),
  ]
  download('applications.csv', lines.join('\n'), 'text/csv')
}

function exportJSON() {
  download('applications.json', JSON.stringify(filteredApps.value, null, 2), 'application/json')
}

// ── Navigation ────────────────────────────────────────────────────────────────

function goToDetail(app: AppListItem) {
  router.push({ name: 'app-detail', params: { normalizedName: app.normalized_name } })
}
</script>

<template>
  <div class="p-6 max-w-[1100px] space-y-5">

    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-[20px] font-bold" style="color: var(--heading);">Applications</h1>
        <p class="text-[12px] mt-0.5" style="color: var(--text-3);">{{ total.toLocaleString() }} distinct applications across the fleet</p>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="exportCSV"
          aria-label="Export as CSV"
          class="text-[11px] font-medium px-2.5 py-1.5 rounded-lg transition-colors"
          style="border: 1px solid var(--border); background: var(--surface); color: var(--text-2);"
        >CSV</button>
        <button
          @click="exportJSON"
          aria-label="Export as JSON"
          class="text-[11px] font-medium px-2.5 py-1.5 rounded-lg transition-colors"
          style="border: 1px solid var(--border); background: var(--surface); color: var(--text-2);"
        >JSON</button>
      </div>
    </div>

    <!-- Filter / search bar -->
    <div class="flex items-center gap-3 flex-wrap">
      <input
        v-model="search"
        type="text"
        placeholder="Search applications…"
        aria-label="Search applications"
        class="text-[12px] px-3 py-2 rounded-lg focus:outline-none focus:ring-1 w-64"
        style="border: 1px solid var(--input-border); background: var(--surface); color: var(--text-1);"
      />

      <!-- Taxonomy filter chips -->
      <div class="flex items-center gap-1">
        <button
          v-for="f in ([
            { key: 'all', label: 'All' },
            { key: 'known', label: `Known (${statKnown})` },
            { key: 'unknown', label: `Unknown (${statUnknown})` },
          ] as const)"
          :key="f.key"
          @click="taxonomyFilter = f.key"
          :aria-pressed="taxonomyFilter === f.key"
          class="px-3 py-1.5 rounded-full text-[11px] font-medium transition-colors"
          :class="taxonomyFilter === f.key
            ? 'bg-[var(--brand-primary)] text-white border-indigo-600'
            : ''"
          :style="taxonomyFilter === f.key ? 'border: 1px solid transparent;' : `background: var(--surface); color: var(--text-2); border: 1px solid var(--border);`"
        >{{ f.label }}</button>
      </div>

      <!-- Page size -->
      <div class="ml-auto flex items-center gap-2 text-[11px]" style="color: var(--text-3);">
        <span>Show</span>
        <select
          v-model.number="limit"
          @change="page = 1; load()"
          aria-label="Page size"
          class="rounded px-2 py-1 text-[11px] focus:outline-none focus:ring-1"
          style="border: 1px solid var(--input-border); background: var(--surface); color: var(--text-2);"
        >
          <option :value="50">50</option>
          <option :value="100">100</option>
          <option :value="250">250</option>
          <option :value="500">500</option>
        </select>
        <span>per page</span>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="isLoading && apps.length === 0" class="flex items-center gap-2 text-[13px] py-10 justify-center" style="color: var(--text-3);">
      <svg class="w-4 h-4 animate-spin text-[var(--brand-primary)]" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
      </svg>
      Loading applications…
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="text-[13px] rounded-xl px-5 py-4"
      style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);"
    >{{ error }}</div>

    <!-- Table -->
    <div v-else class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);" aria-live="polite">
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead style="background: var(--surface-inset); border-bottom: 1px solid var(--border-light);">
            <tr>
              <th scope="col" :aria-sort="sortField === 'name' ? (sortOrder === 'asc' ? 'ascending' : 'descending') : 'none'" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">
                <button @click="toggleSort('name')" class="transition-colors">
                  Application{{ sortIcon('name') }}
                </button>
              </th>
              <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Publisher</th>
              <th scope="col" :aria-sort="sortField === 'agent_count' ? (sortOrder === 'asc' ? 'ascending' : 'descending') : 'none'" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">
                <button @click="toggleSort('agent_count')" class="transition-colors">
                  Agents{{ sortIcon('agent_count') }}
                </button>
              </th>
              <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Category</th>
              <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Lifecycle</th>
              <th scope="col" class="px-4 py-2.5 w-20"></th>
            </tr>
          </thead>
          <tbody class="divide-y" style="--tw-divide-opacity: 1; border-color: var(--border-light);">
            <tr
              v-for="app in filteredApps"
              :key="app.normalized_name"
              class="hover:bg-[var(--info-bg)]/40 transition-colors cursor-pointer group"
              @click="goToDetail(app)"
            >
              <td class="px-4 py-2.5">
                <div class="font-medium" style="color: var(--text-1);">{{ app.display_name }}</div>
                <div class="text-[10px] font-mono mt-0.5" style="color: var(--text-3);">{{ app.normalized_name }}</div>
              </td>
              <td class="px-4 py-2.5" style="color: var(--text-3);">{{ app.publisher || '—' }}</td>
              <td class="px-4 py-2.5 font-medium tabular-nums" style="color: var(--text-2);">{{ app.agent_count }}</td>
              <td class="px-4 py-2.5">
                <span
                  v-if="app.category_display"
                  class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-[var(--info-bg)] text-[var(--info-text)] border border-[var(--border)]"
                >{{ app.category_display }}</span>
                <span
                  v-else
                  class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium"
                  style="background: var(--badge-bg); color: var(--badge-text); border: 1px solid var(--border);"
                >Unknown</span>
              </td>
              <td class="px-4 py-2.5">
                <span
                  v-if="app.eol"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border"
                  :class="app.eol.match_source === 'fuzzy'
                    ? 'bg-[var(--badge-bg)] text-[var(--badge-text)] border-[var(--border)]'
                    : 'bg-orange-500/10 text-orange-600 border-orange-200'"
                  :title="`Tracked by endoflife.date as '${app.eol.eol_product_id}' (${app.eol.match_source}, ${Math.round(app.eol.match_confidence * 100)}%)`"
                >
                  <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {{ app.eol.eol_product_id }}
                </span>
              </td>
              <td class="px-4 py-2.5 text-right">
                <button
                  v-if="!app.category"
                  @click.stop="openTaxModal(app)"
                  title="Add to taxonomy"
                  :aria-label="`Add ${app.display_name} to taxonomy`"
                  class="opacity-0 group-hover:opacity-100 inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium text-[var(--info-text)] hover:bg-[var(--info-bg)] transition-all"
                >
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4" />
                  </svg>
                  Taxonomy
                </button>
              </td>
            </tr>
            <tr v-if="filteredApps.length === 0">
              <td colspan="5" class="px-4 py-8 text-center italic text-[12px]" style="color: var(--text-3);">
                No applications match the current filters.
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="flex items-center justify-between px-4 py-3" style="border-top: 1px solid var(--border-light); background: var(--surface-inset);">
        <p class="text-[11px]" style="color: var(--text-3);">
          Showing {{ (page - 1) * limit + 1 }}–{{ Math.min(page * limit, total) }} of {{ total.toLocaleString() }}
        </p>
        <div class="flex items-center gap-1">
          <button
            :disabled="page <= 1"
            @click="page--"
            aria-label="Previous page"
            class="px-2.5 py-1 rounded text-[11px] font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            style="border: 1px solid var(--border); background: var(--surface); color: var(--text-2);"
          >Prev</button>
          <span class="px-2 text-[11px]" style="color: var(--text-3);">{{ page }} / {{ totalPages }}</span>
          <button
            :disabled="page >= totalPages"
            @click="page++"
            aria-label="Next page"
            class="px-2.5 py-1 rounded text-[11px] font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            style="border: 1px solid var(--border); background: var(--surface); color: var(--text-2);"
          >Next</button>
        </div>
      </div>
    </div>

    <!-- ── Add to taxonomy modal ──────────────────────────────────────────── -->
    <Teleport to="body">
      <div
        v-if="showTaxModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
        @mousedown.self="showTaxModal = false"
      >
        <div class="rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" style="background: var(--surface);" role="dialog" aria-labelledby="tax-modal-title">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4" style="border-bottom: 1px solid var(--border-light);">
            <h3 id="tax-modal-title" class="text-[15px] font-semibold" style="color: var(--heading);">Add to Software Taxonomy</h3>
            <button
              class="p-1.5 rounded-lg transition-colors"
              style="color: var(--text-3);"
              @click="showTaxModal = false"
              aria-label="Close modal"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <form class="px-6 py-5 space-y-4" @submit.prevent="saveTaxEntry">
            <!-- Error -->
            <div v-if="taxError" class="text-[12px] rounded-lg px-3 py-2" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
              {{ taxError }}
            </div>
            <!-- Name -->
            <div>
              <label class="block text-[12px] font-medium mb-1" style="color: var(--text-2);">
                Name <span class="text-[var(--error-text)]">*</span>
              </label>
              <input
                v-model="taxForm.name"
                required
                class="w-full rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-[var(--input-focus)] focus:border-transparent"
                style="border: 1px solid var(--input-border); background: var(--surface); color: var(--text-1);"
              />
            </div>

            <!-- Patterns -->
            <div>
              <label class="block text-[12px] font-medium mb-1" style="color: var(--text-2);">
                Patterns <span class="text-[var(--error-text)]">*</span>
                <span class="font-normal ml-1" style="color: var(--text-3);">(one per line, glob syntax)</span>
              </label>
              <textarea
                v-model="taxForm.patterns"
                required
                rows="2"
                class="w-full rounded-lg px-3 py-2 text-[13px] font-mono focus:outline-none focus:ring-2 focus:ring-[var(--input-focus)] focus:border-transparent resize-none"
                style="border: 1px solid var(--input-border); background: var(--surface); color: var(--text-1);"
              />
            </div>

            <!-- Category selector -->
            <div>
              <label class="block text-[12px] font-medium mb-1.5" style="color: var(--text-2);">
                Category <span class="text-[var(--error-text)]">*</span>
              </label>
              <!-- Quick-select from existing categories -->
              <div v-if="taxCategories.length > 0" class="flex flex-wrap gap-1.5 mb-2">
                <button
                  v-for="cat in taxCategories"
                  :key="cat.key"
                  type="button"
                  @click="selectCategory(cat)"
                  class="px-2.5 py-1 rounded-full text-[11px] font-medium transition-colors"
                  :class="taxForm.category === cat.key
                    ? 'bg-[var(--brand-primary)] text-white border-indigo-600'
                    : ''"
                  :style="taxForm.category === cat.key ? 'border: 1px solid transparent;' : `background: var(--surface); color: var(--text-2); border: 1px solid var(--border);`"
                >{{ cat.display }}</button>
              </div>
              <!-- Or type a new one -->
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <input
                    v-model="taxForm.category"
                    required
                    placeholder="Category key (e.g. devtools)"
                    class="w-full rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-[var(--input-focus)] focus:border-transparent"
                    style="border: 1px solid var(--input-border); background: var(--surface); color: var(--text-1);"
                  />
                </div>
                <div>
                  <input
                    v-model="taxForm.category_display"
                    placeholder="Label (e.g. Developer Tools)"
                    class="w-full rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-[var(--input-focus)] focus:border-transparent"
                    style="border: 1px solid var(--input-border); background: var(--surface); color: var(--text-1);"
                  />
                </div>
              </div>
            </div>

            <!-- Publisher -->
            <div>
              <label class="block text-[12px] font-medium mb-1" style="color: var(--text-2);">Publisher</label>
              <input
                v-model="taxForm.publisher"
                placeholder="Optional"
                class="w-full rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-[var(--input-focus)] focus:border-transparent"
                style="border: 1px solid var(--input-border); background: var(--surface); color: var(--text-1);"
              />
            </div>

            <div class="flex justify-end gap-2 pt-1">
              <button
                type="button"
                class="px-4 py-2 rounded-lg text-[13px] font-medium transition-colors"
                style="background: var(--badge-bg); color: var(--text-2);"
                @click="showTaxModal = false"
              >Cancel</button>
              <button
                type="submit"
                :disabled="taxSaving"
                class="px-4 py-2 rounded-lg text-[13px] font-medium text-white bg-[var(--brand-primary)] hover:opacity-90 disabled:opacity-50 transition-colors"
              >{{ taxSaving ? 'Saving…' : 'Add to Taxonomy' }}</button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

  </div>
</template>
