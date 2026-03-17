<!--
  LibraryBrowserView — browse and search shared fingerprint library entries.
  Features: stat bar, filters (search, source, status), card grid, pagination,
  create entry modal for analyst/admin roles.
-->
<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/useAuthStore'
import { useDeployment } from '@/composables/useDeployment'
import * as libraryApi from '@/api/library'
import type { LibraryEntry, LibraryEntryCreateRequest, LibraryStatsResponse } from '@/types/library'

const router = useRouter()
const auth = useAuthStore()
const { isOnprem } = useDeployment()

// ── State ─────────────────────────────────────────────────────────────────────

const entries = ref<LibraryEntry[]>([])
const total = ref(0)
const stats = ref<LibraryStatsResponse | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)

// Filters
const search = ref('')
const sourceFilter = ref('')
const statusFilter = ref('published')
const page = ref(1)
const pageSize = ref(24)

// Create modal
const showCreateModal = ref(false)
const createForm = ref({ name: '', vendor: '', category: '', description: '', tags: '' })
const isCreating = ref(false)
const createError = ref<string | null>(null)

// ── Data loading ──────────────────────────────────────────────────────────────

let searchTimeout: ReturnType<typeof setTimeout> | null = null

async function loadEntries() {
  isLoading.value = true
  error.value = null
  try {
    const params: Record<string, string | number> = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (search.value) params.search = search.value
    if (sourceFilter.value) params.source = sourceFilter.value
    if (statusFilter.value) params.status = statusFilter.value

    const res = await libraryApi.listEntries(params)
    entries.value = res.entries
    total.value = res.total
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load library entries'
  } finally {
    isLoading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = await libraryApi.getStats()
  } catch {
    // Stats are non-critical — silently ignore
  }
}

onMounted(() => {
  loadEntries()
  loadStats()
})

watch(search, () => {
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    page.value = 1
    loadEntries()
  }, 300)
})

watch([sourceFilter, statusFilter], () => {
  page.value = 1
  loadEntries()
})

watch(page, loadEntries)

onUnmounted(() => {
  if (searchTimeout) clearTimeout(searchTimeout)
})

// ── Computed ──────────────────────────────────────────────────────────────────

const totalPages = computed(() => Math.ceil(total.value / pageSize.value))
const canCreate = computed(() => auth.user?.role === 'admin' || auth.user?.role === 'analyst')

const sources = [
  { key: '', label: 'All Sources' },
  { key: 'nist_cpe', label: 'NIST CPE' },
  { key: 'mitre', label: 'MITRE' },
  { key: 'chocolatey', label: 'Chocolatey' },
  { key: 'homebrew', label: 'Homebrew' },
  { key: 'manual', label: 'Manual' },
]

const statuses = [
  { key: '', label: 'All' },
  { key: 'published', label: 'Published' },
  { key: 'draft', label: 'Draft' },
  { key: 'deprecated', label: 'Deprecated' },
]

// ── Helpers ───────────────────────────────────────────────────────────────────

function sourceBadgeClass(source: string): string {
  switch (source) {
    case 'nist_cpe': return 'bg-[var(--info-bg)] text-[var(--info-text)] border-[var(--border)]'
    case 'mitre': return 'bg-purple-50 text-purple-700 border-purple-200'
    case 'chocolatey': return 'bg-[var(--warn-bg)] text-[var(--warn-text)] border-[var(--warn-border)]'
    case 'homebrew': return 'bg-[var(--success-bg)] text-[var(--success-text)] border-[var(--success-border)]'
    case 'manual': return 'badge-neutral border'
    default: return 'badge-neutral border'
  }
}

function sourceLabel(source: string): string {
  const found = sources.find((s) => s.key === source)
  return found ? found.label : source
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case 'published': return 'bg-[var(--success-bg)] text-[var(--success-text)] border-[var(--success-border)]'
    case 'draft': return 'bg-[var(--warn-bg)] text-[var(--warn-text)] border-[var(--warn-border)]'
    case 'deprecated': return 'bg-[var(--error-bg)] text-[var(--error-text)] border-[var(--error-border)]'
    default: return 'badge-neutral border'
  }
}

function goToEntry(entry: LibraryEntry) {
  router.push({ name: 'library-entry', params: { entryId: entry.id } })
}

// ── Create entry ──────────────────────────────────────────────────────────────

function openCreateModal() {
  createForm.value = { name: '', vendor: '', category: '', description: '', tags: '' }
  createError.value = null
  showCreateModal.value = true
}

async function handleCreate() {
  createError.value = null
  if (!createForm.value.name.trim()) {
    createError.value = 'Name is required'
    return
  }

  isCreating.value = true
  try {
    const payload: LibraryEntryCreateRequest = {
      name: createForm.value.name.trim(),
    }
    if (createForm.value.vendor.trim()) payload.vendor = createForm.value.vendor.trim()
    if (createForm.value.category.trim()) payload.category = createForm.value.category.trim()
    if (createForm.value.description.trim()) payload.description = createForm.value.description.trim()
    if (createForm.value.tags.trim()) {
      payload.tags = createForm.value.tags.split(',').map((t) => t.trim()).filter(Boolean)
    }

    const entry = await libraryApi.createEntry(payload)
    showCreateModal.value = false
    router.push({ name: 'library-entry', params: { entryId: entry.id } })
  } catch (e) {
    createError.value = e instanceof Error ? e.message : 'Failed to create entry'
  } finally {
    isCreating.value = false
  }
}
</script>

<template>
  <div class="p-6 max-w-[1100px] space-y-6">

    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-[20px] font-bold" style="color: var(--heading);">Fingerprint Library</h1>
        <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Browse and subscribe to shared fingerprint definitions</p>
      </div>
      <button
        v-if="canCreate"
        class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[var(--brand-primary)] text-white text-[13px] font-medium hover:opacity-90 transition-colors"
        aria-label="Create new library entry"
        @click="openCreateModal"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        Create Entry
      </button>
    </div>

    <!-- Stats bar -->
    <div v-if="stats" class="grid grid-cols-2 sm:grid-cols-4 gap-4" aria-label="Library statistics">
      <div class="rounded-xl px-4 py-3 shadow-sm" style="background: var(--surface); border: 1px solid var(--border);">
        <p class="text-[11px] font-medium uppercase tracking-wider" style="color: var(--text-3);">Total Entries</p>
        <p class="text-[22px] font-bold mt-1 tabular-nums" style="color: var(--text-1);">{{ stats.total_entries.toLocaleString() }}</p>
      </div>
      <div class="rounded-xl px-4 py-3 shadow-sm" style="background: var(--surface); border: 1px solid var(--border);">
        <p class="text-[11px] font-medium uppercase tracking-wider" style="color: var(--text-3);">Subscriptions</p>
        <p class="text-[22px] font-bold mt-1 tabular-nums" style="color: var(--text-1);">{{ stats.total_subscriptions.toLocaleString() }}</p>
      </div>
      <div class="rounded-xl px-4 py-3 shadow-sm" style="background: var(--surface); border: 1px solid var(--border);">
        <p class="text-[11px] font-medium uppercase tracking-wider" style="color: var(--text-3);">By Source</p>
        <div class="flex flex-wrap gap-1.5 mt-2">
          <span
            v-for="(count, source) in stats.by_source"
            :key="source"
            class="text-[10px] font-medium px-1.5 py-0.5 rounded-full border"
            :class="sourceBadgeClass(String(source))"
          >{{ sourceLabel(String(source)) }}: {{ count }}</span>
        </div>
      </div>
      <div class="rounded-xl px-4 py-3 shadow-sm" style="background: var(--surface); border: 1px solid var(--border);">
        <p class="text-[11px] font-medium uppercase tracking-wider" style="color: var(--text-3);">By Status</p>
        <div class="flex flex-wrap gap-1.5 mt-2">
          <span
            v-for="(count, status) in stats.by_status"
            :key="status"
            class="text-[10px] font-medium px-1.5 py-0.5 rounded-full border"
            :class="statusBadgeClass(String(status))"
          >{{ String(status) }}: {{ count }}</span>
        </div>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-3 flex-wrap">
      <input
        v-model="search"
        type="text"
        placeholder="Search entries..."
        aria-label="Search library entries"
        class="text-[12px] px-3 py-2 rounded-lg focus:outline-none focus:ring-1 placeholder-[var(--text-3)] w-64"
        style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
      />

      <select
        v-model="sourceFilter"
        aria-label="Filter by source"
        class="rounded-lg px-3 py-2 text-[12px] focus:outline-none focus:ring-1"
        style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-2);"
      >
        <option v-for="s in sources" :key="s.key" :value="s.key">{{ s.label }}</option>
      </select>

      <div class="flex items-center gap-1">
        <button
          v-for="s in statuses"
          :key="s.key"
          @click="statusFilter = s.key"
          :aria-pressed="statusFilter === s.key"
          class="px-3 py-1.5 rounded-full text-[11px] font-medium transition-colors border"
          :class="statusFilter === s.key
            ? 'bg-[var(--brand-primary)] text-white border-indigo-600'
            : 'hover:border-[var(--border)]'"
          :style="statusFilter !== s.key ? 'background: var(--surface); color: var(--text-2); border-color: var(--border);' : ''"
        >{{ s.label }}</button>
      </div>

      <router-link
        v-if="(isOnprem && auth.isAdmin) || auth.isSuperAdmin"
        to="/library/sources"
        class="ml-auto text-[11px] font-medium text-[var(--info-text)] hover:text-[var(--heading)] transition-colors no-underline"
        aria-label="Manage library sources"
      >Manage Sources</router-link>
    </div>

    <!-- Loading -->
    <div v-if="isLoading && entries.length === 0" class="flex items-center gap-2 text-[13px] py-10 justify-center" style="color: var(--text-3);">
      <svg class="w-4 h-4 animate-spin text-[var(--brand-primary)]" fill="none" viewBox="0 0 24 24" aria-hidden="true">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
      </svg>
      Loading library entries...
    </div>

    <!-- Error -->
    <div v-else-if="error" class="text-[13px] rounded-xl px-5 py-4" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
      {{ error }}
    </div>

    <!-- Empty state -->
    <div v-else-if="entries.length === 0 && !isLoading" class="text-center py-16">
      <div class="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4" style="background: var(--surface-inset);">
        <svg class="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" aria-hidden="true" style="color: var(--text-3);">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
      </div>
      <p class="text-[14px] font-medium mb-1" style="color: var(--text-2);">No library entries found</p>
      <p class="text-[12px]" style="color: var(--text-3);">Try adjusting your filters or create a new entry.</p>
    </div>

    <!-- Entry cards grid -->
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" aria-live="polite">
      <button
        v-for="entry in entries"
        :key="entry.id"
        @click="goToEntry(entry)"
        class="rounded-xl shadow-sm hover:shadow-md hover:border-[var(--border)] transition-all p-4 text-left cursor-pointer group"
        style="background: var(--surface); border: 1px solid var(--border);"
        :aria-label="`View library entry: ${entry.name}`"
      >
        <!-- Top: name + status -->
        <div class="flex items-start justify-between gap-2 mb-2">
          <h3 class="text-[14px] font-semibold group-hover:text-[var(--info-text)] transition-colors leading-snug line-clamp-2" style="color: var(--text-1);">{{ entry.name }}</h3>
          <span
            class="shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded-full border"
            :class="statusBadgeClass(entry.status)"
          >{{ entry.status }}</span>
        </div>

        <!-- Vendor -->
        <p v-if="entry.vendor" class="text-[11px] mb-2 truncate" style="color: var(--text-3);">{{ entry.vendor }}</p>

        <!-- Description -->
        <p v-if="entry.description" class="text-[12px] mb-3 line-clamp-2 leading-relaxed" style="color: var(--text-3);">{{ entry.description }}</p>

        <!-- Source badge + marker count + subscriber count -->
        <div class="flex items-center gap-2 mb-2.5">
          <span
            class="text-[10px] font-medium px-1.5 py-0.5 rounded-full border"
            :class="sourceBadgeClass(entry.source)"
          >{{ sourceLabel(entry.source) }}</span>
          <span class="text-[10px]" style="color: var(--text-3);">
            <svg class="w-3 h-3 inline-block mr-0.5 -mt-px" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
            </svg>
            {{ entry.markers.length }} markers
          </span>
          <span class="text-[10px]" style="color: var(--text-3);">
            <svg class="w-3 h-3 inline-block mr-0.5 -mt-px" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            {{ entry.subscriber_count }}
          </span>
        </div>

        <!-- Tags -->
        <div v-if="entry.tags.length > 0" class="flex flex-wrap gap-1">
          <span
            v-for="tag in entry.tags.slice(0, 5)"
            :key="tag"
            class="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-[var(--info-bg)] text-[var(--info-text)] border border-[var(--border-light)]"
          >{{ tag }}</span>
          <span
            v-if="entry.tags.length > 5"
            class="text-[10px]" style="color: var(--text-3);"
          >+{{ entry.tags.length - 5 }} more</span>
        </div>
      </button>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="flex items-center justify-between">
      <p class="text-[11px]" style="color: var(--text-3);">
        Showing {{ (page - 1) * pageSize + 1 }}–{{ Math.min(page * pageSize, total) }} of {{ total.toLocaleString() }}
      </p>
      <div class="flex items-center gap-1">
        <button
          :disabled="page <= 1"
          @click="page--"
          aria-label="Previous page"
          class="px-2.5 py-1 rounded text-[11px] font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          style="background: var(--surface); border: 1px solid var(--border); color: var(--text-2);"
        >Prev</button>
        <span class="px-2 text-[11px]" style="color: var(--text-3);">{{ page }} / {{ totalPages }}</span>
        <button
          :disabled="page >= totalPages"
          @click="page++"
          aria-label="Next page"
          class="px-2.5 py-1 rounded text-[11px] font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          style="background: var(--surface); border: 1px solid var(--border); color: var(--text-2);"
        >Next</button>
      </div>
    </div>

    <!-- ── Create entry modal ──────────────────────────────────────────────── -->
    <Teleport to="body">
      <div
        v-if="showCreateModal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        style="background: rgba(15,20,36,0.5)"
        @click.self="showCreateModal = false"
      >
        <div
          class="rounded-2xl shadow-2xl w-full max-w-md overflow-hidden"
          style="background: var(--surface);"
          role="dialog"
          aria-modal="true"
          aria-label="Create library entry"
        >
          <!-- Modal header -->
          <div class="flex items-center justify-between px-5 py-4" style="border-bottom: 1px solid var(--border);">
            <h3 class="text-[15px] font-semibold" style="color: var(--text-1);">New Library Entry</h3>
            <button
              class="w-7 h-7 flex items-center justify-center rounded-lg transition-colors text-[18px] leading-none"
              style="color: var(--text-3);"
              aria-label="Close dialog"
              @click="showCreateModal = false"
            >&times;</button>
          </div>

          <!-- Form -->
          <div class="px-5 py-4 space-y-4">
            <div v-if="createError" class="px-3 py-2 text-sm rounded-lg" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
              {{ createError }}
            </div>

            <!-- Name -->
            <div>
              <label for="lib-name" class="block text-xs font-medium mb-1" style="color: var(--text-2);">Name <span class="text-[var(--error-text)]">*</span></label>
              <input
                id="lib-name"
                v-model="createForm.name"
                type="text"
                placeholder="e.g. Google Chrome"
                class="w-full px-3 py-2 text-sm rounded-lg outline-none transition" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              />
            </div>

            <!-- Vendor -->
            <div>
              <label for="lib-vendor" class="block text-xs font-medium mb-1" style="color: var(--text-2);">Vendor</label>
              <input
                id="lib-vendor"
                v-model="createForm.vendor"
                type="text"
                placeholder="e.g. Google LLC"
                class="w-full px-3 py-2 text-sm rounded-lg outline-none transition" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              />
            </div>

            <!-- Category -->
            <div>
              <label for="lib-category" class="block text-xs font-medium mb-1" style="color: var(--text-2);">Category</label>
              <input
                id="lib-category"
                v-model="createForm.category"
                type="text"
                placeholder="e.g. browser"
                class="w-full px-3 py-2 text-sm rounded-lg outline-none transition" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              />
            </div>

            <!-- Description -->
            <div>
              <label for="lib-desc" class="block text-xs font-medium mb-1" style="color: var(--text-2);">Description</label>
              <textarea
                id="lib-desc"
                v-model="createForm.description"
                rows="2"
                placeholder="Brief description of this software"
                class="w-full px-3 py-2 text-sm rounded-lg outline-none transition resize-none" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              />
            </div>

            <!-- Tags -->
            <div>
              <label for="lib-tags" class="block text-xs font-medium mb-1" style="color: var(--text-2);">
                Tags <span class="font-normal" style="color: var(--text-3);">(comma-separated)</span>
              </label>
              <input
                id="lib-tags"
                v-model="createForm.tags"
                type="text"
                placeholder="e.g. web, productivity, security"
                class="w-full px-3 py-2 text-sm rounded-lg outline-none transition" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              />
            </div>
          </div>

          <!-- Footer -->
          <div class="px-5 py-3 flex items-center justify-end gap-2" style="background: var(--surface-inset); border-top: 1px solid var(--border);">
            <button
              class="px-4 py-1.5 rounded-lg text-[13px] font-medium transition-colors"
              style="background: var(--surface-hover); color: var(--text-2);"
              @click="showCreateModal = false"
            >Cancel</button>
            <button
              class="px-4 py-1.5 rounded-lg bg-[var(--brand-primary)] text-white text-[13px] font-medium hover:opacity-90 transition-colors disabled:opacity-50"
              :disabled="isCreating"
              @click="handleCreate"
            >{{ isCreating ? 'Creating...' : 'Create' }}</button>
          </div>
        </div>
      </div>
    </Teleport>

  </div>
</template>
