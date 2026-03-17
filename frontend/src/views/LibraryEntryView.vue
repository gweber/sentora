<!--
  LibraryEntryView — detail page for a single fingerprint library entry.
  Shows entry metadata, markers table, subscription management, and admin actions.
-->
<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/useAuthStore'
import * as libraryApi from '@/api/library'
import type { LibraryEntry, LibraryEntryUpdateRequest } from '@/types/library'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

// ── State ─────────────────────────────────────────────────────────────────────

const entry = ref<LibraryEntry | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)
const actionLoading = ref<string | null>(null)
const actionError = ref<string | null>(null)

// Subscribe modal
const showSubscribeModal = ref(false)
const subscribeGroupId = ref('')
const subscribeAutoUpdate = ref(true)
const subscribing = ref(false)
const subscribeError = ref<string | null>(null)

// Edit modal
const showEditModal = ref(false)
const editForm = ref({ name: '', vendor: '', category: '', description: '', tags: '' })
const isEditing = ref(false)
const editError = ref<string | null>(null)

// Delete confirmation
const showDeleteConfirm = ref(false)

// ── Computed ──────────────────────────────────────────────────────────────────

const entryId = computed(() => route.params.entryId as string)
const isAdmin = computed(() => auth.user?.role === 'admin')
const canEdit = computed(() => auth.user?.role === 'admin' || auth.user?.role === 'analyst')

// ── Data loading ──────────────────────────────────────────────────────────────

async function loadEntry() {
  isLoading.value = true
  error.value = null
  try {
    entry.value = await libraryApi.getEntry(entryId.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load library entry'
  } finally {
    isLoading.value = false
  }
}

onMounted(loadEntry)

watch(entryId, (newId, oldId) => {
  if (newId && newId !== oldId) loadEntry()
})

onUnmounted(() => {
  if (_promoteClearTimer) clearTimeout(_promoteClearTimer)
})

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
  const map: Record<string, string> = {
    nist_cpe: 'NIST CPE',
    mitre: 'MITRE',
    chocolatey: 'Chocolatey',
    homebrew: 'Homebrew',
    manual: 'Manual',
  }
  return map[source] ?? source
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case 'published': return 'bg-[var(--success-bg)] text-[var(--success-text)] border-[var(--success-border)]'
    case 'draft': return 'bg-[var(--warn-bg)] text-[var(--warn-text)] border-[var(--warn-border)]'
    case 'deprecated': return 'bg-[var(--error-bg)] text-[var(--error-text)] border-[var(--error-border)]'
    default: return 'badge-neutral border'
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function weightColor(weight: number): string {
  if (weight >= 0.7) return 'text-[var(--success-text)] bg-[var(--success-bg)]'
  if (weight >= 0.4) return 'text-[var(--warn-text)] bg-[var(--warn-bg)]'
  return 'badge-neutral-muted'
}

// ── Actions ───────────────────────────────────────────────────────────────────

async function handlePublish() {
  actionLoading.value = 'publish'
  actionError.value = null
  try {
    entry.value = await libraryApi.publishEntry(entryId.value)
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : 'Publish failed'
  } finally {
    actionLoading.value = null
  }
}

async function handleDeprecate() {
  actionLoading.value = 'deprecate'
  actionError.value = null
  try {
    entry.value = await libraryApi.deprecateEntry(entryId.value)
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : 'Deprecate failed'
  } finally {
    actionLoading.value = null
  }
}

// Promote to Taxonomy
const showPromotePanel = ref(false)
const promotePreview = ref<Awaited<ReturnType<typeof libraryApi.promotePreview>> | null>(null)
const promoteCategory = ref('')
const promoteResult = ref<{ created: boolean; patterns_added: number } | null>(null)
const promoteLoading = ref(false)
let _promoteClearTimer: ReturnType<typeof setTimeout> | null = null

async function handleShowPromotePanel() {
  showPromotePanel.value = true
  promotePreview.value = null
  promoteResult.value = null
  try {
    const preview = await libraryApi.promotePreview(entryId.value)
    promotePreview.value = preview
    promoteCategory.value = preview.category
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : 'Failed to load preview'
    showPromotePanel.value = false
  }
}

async function handlePromoteToTaxonomy() {
  promoteLoading.value = true
  actionError.value = null
  promoteResult.value = null
  try {
    const result = await libraryApi.promoteToTaxonomy(entryId.value, promoteCategory.value)
    promoteResult.value = result
    showPromotePanel.value = false
    if (_promoteClearTimer) clearTimeout(_promoteClearTimer)
    _promoteClearTimer = setTimeout(() => {
      promoteResult.value = null
      _promoteClearTimer = null
    }, 5000)
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : 'Promote to taxonomy failed'
  } finally {
    promoteLoading.value = false
  }
}

async function handleDelete() {
  actionLoading.value = 'delete'
  actionError.value = null
  try {
    await libraryApi.deleteEntry(entryId.value)
    router.push({ name: 'library' })
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : 'Delete failed'
    showDeleteConfirm.value = false
  } finally {
    actionLoading.value = null
  }
}

// ── Subscribe ─────────────────────────────────────────────────────────────────

function openSubscribeModal() {
  subscribeGroupId.value = ''
  subscribeAutoUpdate.value = true
  subscribeError.value = null
  showSubscribeModal.value = true
}

async function handleSubscribe() {
  subscribeError.value = null
  if (!subscribeGroupId.value.trim()) {
    subscribeError.value = 'Group ID is required'
    return
  }

  subscribing.value = true
  try {
    await libraryApi.subscribeGroup(entryId.value, subscribeGroupId.value.trim(), subscribeAutoUpdate.value)
    showSubscribeModal.value = false
    await loadEntry()
  } catch (e) {
    subscribeError.value = e instanceof Error ? e.message : 'Subscription failed'
  } finally {
    subscribing.value = false
  }
}

// ── Edit ──────────────────────────────────────────────────────────────────────

function openEditModal() {
  if (!entry.value) return
  editForm.value = {
    name: entry.value.name,
    vendor: entry.value.vendor,
    category: entry.value.category,
    description: entry.value.description,
    tags: entry.value.tags.join(', '),
  }
  editError.value = null
  showEditModal.value = true
}

async function handleEdit() {
  editError.value = null
  if (!editForm.value.name.trim()) {
    editError.value = 'Name is required'
    return
  }

  isEditing.value = true
  try {
    const payload: LibraryEntryUpdateRequest = {
      name: editForm.value.name.trim(),
      vendor: editForm.value.vendor.trim(),
      category: editForm.value.category.trim(),
      description: editForm.value.description.trim(),
      tags: editForm.value.tags.split(',').map((t) => t.trim()).filter(Boolean),
    }
    entry.value = await libraryApi.updateEntry(entryId.value, payload)
    showEditModal.value = false
  } catch (e) {
    editError.value = e instanceof Error ? e.message : 'Update failed'
  } finally {
    isEditing.value = false
  }
}
</script>

<template>
  <div class="p-6 max-w-[960px] space-y-6">

    <!-- Back link -->
    <router-link
      to="/library"
      class="inline-flex items-center gap-1 text-[12px] hover:text-[var(--info-text)] transition-colors no-underline"
      style="color: var(--text-3);"
      aria-label="Back to library browser"
    >
      <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
      </svg>
      Back to Library
    </router-link>

    <!-- Loading -->
    <div v-if="isLoading" class="flex items-center gap-2 text-[13px] py-10 justify-center" style="color: var(--text-3);">
      <svg class="w-4 h-4 animate-spin text-[var(--brand-primary)]" fill="none" viewBox="0 0 24 24" aria-hidden="true">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
      </svg>
      Loading entry...
    </div>

    <!-- Error -->
    <div v-else-if="error" class="text-[13px] rounded-xl px-5 py-4" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
      {{ error }}
    </div>

    <!-- Entry detail -->
    <template v-else-if="entry">

      <!-- Header -->
      <div class="rounded-xl shadow-sm p-5" style="background: var(--surface); border: 1px solid var(--border);">
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2.5 mb-2">
              <h1 class="text-[20px] font-bold" style="color: var(--heading);">{{ entry.name }}</h1>
              <span
                class="text-[11px] font-medium px-2 py-0.5 rounded-full border"
                :class="statusBadgeClass(entry.status)"
              >{{ entry.status }}</span>
              <span
                class="text-[11px] font-medium px-2 py-0.5 rounded-full border"
                :class="sourceBadgeClass(entry.source)"
              >{{ sourceLabel(entry.source) }}</span>
            </div>
            <p v-if="entry.vendor" class="text-[13px] mb-1" style="color: var(--text-3);">{{ entry.vendor }}</p>
            <p v-if="entry.description" class="text-[13px] leading-relaxed mb-3" style="color: var(--text-3);">{{ entry.description }}</p>

            <!-- Tags -->
            <div v-if="entry.tags.length > 0" class="flex flex-wrap gap-1.5 mb-3">
              <span
                v-for="tag in entry.tags"
                :key="tag"
                class="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-[var(--info-bg)] text-[var(--info-text)] border border-[var(--border-light)]"
              >{{ tag }}</span>
            </div>

            <!-- Meta info -->
            <div class="flex items-center gap-4 text-[11px]" style="color: var(--text-3);">
              <span>Version {{ entry.version }}</span>
              <span>{{ entry.subscriber_count }} subscribers</span>
              <span>Created {{ formatDate(entry.created_at) }}</span>
              <span>Updated {{ formatDate(entry.updated_at) }}</span>
              <span v-if="entry.submitted_by">By {{ entry.submitted_by }}</span>
              <span v-if="entry.reviewed_by">Reviewed by {{ entry.reviewed_by }}</span>
            </div>
          </div>

          <!-- Action buttons -->
          <div v-if="canEdit" class="flex items-center gap-1.5 shrink-0">
            <button
              class="px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors"
              style="background: var(--surface); color: var(--text-2); border: 1px solid var(--border);"
              aria-label="Edit entry"
              @click="openEditModal"
            >Edit</button>
            <button
              class="px-2.5 py-1 rounded-md text-[11px] font-medium bg-[var(--info-bg)] text-[var(--info-text)] border border-[var(--border)] hover:bg-[var(--info-bg)] transition-colors"
              aria-label="Subscribe a group"
              @click="openSubscribeModal"
            >Subscribe Group</button>
            <button
              v-if="isAdmin && entry.status === 'draft'"
              class="px-2.5 py-1 rounded-md text-[11px] font-medium bg-[var(--success-bg)] text-[var(--success-text)] border border-[var(--success-border)] hover:bg-[var(--success-bg)] transition-colors"
              :disabled="actionLoading === 'publish'"
              aria-label="Publish entry"
              @click="handlePublish"
            >{{ actionLoading === 'publish' ? 'Publishing...' : 'Publish' }}</button>
            <button
              v-if="isAdmin && entry.status === 'published'"
              class="px-2.5 py-1 rounded-md text-[11px] font-medium bg-[var(--warn-bg)] text-[var(--warn-text)] border border-[var(--warn-border)] hover:bg-[var(--warn-bg)] transition-colors"
              :disabled="actionLoading === 'deprecate'"
              aria-label="Deprecate entry"
              @click="handleDeprecate"
            >{{ actionLoading === 'deprecate' ? 'Deprecating...' : 'Deprecate' }}</button>
            <button
              v-if="isAdmin && entry.markers.length > 0"
              class="px-2.5 py-1 rounded-md text-[11px] font-medium bg-[var(--info-bg)] text-[var(--info-text)] border border-[var(--border)] hover:bg-[var(--info-bg)] transition-colors"
              aria-label="Add to taxonomy catalog"
              @click="handleShowPromotePanel"
            >Add to Taxonomy</button>
            <span
              v-if="promoteResult"
              class="text-[11px] font-medium"
              :class="promoteResult.created ? 'text-[var(--success-text)]' : 'text-[var(--info-text)]'"
            >{{ promoteResult.created ? `Created (${promoteResult.patterns_added} patterns)` : `Merged ${promoteResult.patterns_added} patterns` }}</span>
            <button
              v-if="isAdmin"
              class="px-2.5 py-1 rounded-md text-[11px] font-medium text-[var(--error-text)] hover:bg-[var(--error-bg)] hover:border-[var(--error-border)] transition-colors"
              style="background: var(--surface); border: 1px solid var(--border);"
              aria-label="Delete entry"
              @click="showDeleteConfirm = true"
            >Delete</button>
          </div>
        </div>

        <div v-if="actionError" class="mt-3 px-3 py-2 text-sm rounded-lg" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
          {{ actionError }}
        </div>
      </div>

      <!-- Promote to Taxonomy panel -->
      <div
        v-if="showPromotePanel && promotePreview"
        class="rounded-xl shadow-sm overflow-hidden"
        style="background: var(--surface); border: 1px solid var(--border);"
      >
        <div class="px-5 py-3 flex items-center justify-between" style="border-bottom: 1px solid var(--border-light); background: var(--surface-inset);">
          <h2 class="text-[14px] font-semibold" style="color: var(--text-1);">Add to Taxonomy</h2>
          <button class="text-[11px] text-muted hover:text-[var(--info-text)]" @click="showPromotePanel = false">Cancel</button>
        </div>
        <div class="p-5 space-y-4">
          <!-- Merge warning -->
          <div v-if="promotePreview.would_merge" class="px-3 py-2 rounded-lg text-[12px] bg-[var(--warn-bg)] text-amber-800 border border-[var(--warn-border)]">
            A taxonomy entry named "<strong>{{ promotePreview.existing_entry_name }}</strong>" already exists.
            {{ promotePreview.new_patterns.length }} new pattern(s) will be merged.
          </div>

          <!-- Category selector -->
          <div>
            <label class="block text-[12px] font-medium mb-1.5" style="color: var(--text-2);">Taxonomy Category</label>
            <select
              v-model="promoteCategory"
              class="w-full max-w-xs px-3 py-1.5 rounded-lg border text-[13px] focus:outline-none focus:ring-2 focus:ring-[var(--input-focus)]/30"
              style="background: var(--surface); border-color: var(--border); color: var(--text-1);"
            >
              <option
                v-for="cat in promotePreview.available_categories"
                :key="cat.key"
                :value="cat.key"
              >{{ cat.display }}</option>
              <!-- Allow the default mapping if it's not in the list -->
              <option
                v-if="promotePreview && !promotePreview.available_categories.some(c => c.key === promotePreview!.category)"
                :value="promotePreview.category"
              >{{ promotePreview.category_display }} (new)</option>
            </select>
          </div>

          <!-- Patterns preview -->
          <div>
            <label class="block text-[12px] font-medium mb-1.5" style="color: var(--text-2);">
              Patterns ({{ promotePreview.would_merge ? promotePreview.new_patterns.length + ' new' : promotePreview.patterns.length }})
            </label>
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="p in (promotePreview.would_merge ? promotePreview.new_patterns : promotePreview.patterns)"
                :key="p"
                class="px-2 py-0.5 rounded text-[11px] font-mono badge-neutral border"
              >{{ p }}</span>
              <span v-if="(promotePreview.would_merge ? promotePreview.new_patterns : promotePreview.patterns).length === 0" class="text-[12px] text-muted">
                No new patterns to add
              </span>
            </div>
          </div>

          <!-- Confirm button -->
          <div class="flex items-center gap-3 pt-1">
            <button
              :disabled="promoteLoading || (promotePreview.would_merge && promotePreview.new_patterns.length === 0)"
              class="px-4 py-1.5 rounded-lg bg-[var(--brand-primary)] text-white text-[12px] font-medium hover:opacity-90 transition-colors disabled:opacity-40"
              @click="handlePromoteToTaxonomy"
            >{{ promoteLoading ? 'Adding...' : promotePreview.would_merge ? 'Merge Patterns' : 'Create Entry' }}</button>
            <button class="px-3 py-1.5 rounded-lg text-[12px] text-muted border-muted border hover:border-[var(--border)] transition-colors" style="background: var(--surface);" @click="showPromotePanel = false">Cancel</button>
          </div>
        </div>
      </div>

      <!-- Markers table -->
      <div class="rounded-xl shadow-sm overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
        <div class="px-5 py-3" style="border-bottom: 1px solid var(--border-light); background: var(--surface-inset);">
          <h2 class="text-[14px] font-semibold" style="color: var(--text-1);">Markers ({{ entry.markers.length }})</h2>
        </div>

        <div v-if="entry.markers.length === 0" class="px-5 py-8 text-center text-[12px] italic" style="color: var(--text-3);">
          No markers defined for this entry.
        </div>

        <div v-else class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead style="background: var(--surface-inset); border-bottom: 1px solid var(--border-light);">
              <tr>
                <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Pattern</th>
                <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Display Name</th>
                <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Category</th>
                <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Weight</th>
                <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Source Detail</th>
                <th scope="col" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">Added</th>
              </tr>
            </thead>
            <tbody class="divide-y" style="--tw-divide-opacity: 1; border-color: var(--border-light);">
              <tr
                v-for="marker in entry.markers"
                :key="marker.id"
                class="hover:bg-[var(--info-bg)]/40 transition-colors"
              >
                <td class="px-4 py-2.5 font-mono text-[11px]" style="color: var(--text-1);">{{ marker.pattern }}</td>
                <td class="px-4 py-2.5" style="color: var(--text-2);">{{ marker.display_name || '—' }}</td>
                <td class="px-4 py-2.5" style="color: var(--text-3);">{{ marker.category || '—' }}</td>
                <td class="px-4 py-2.5">
                  <span
                    class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium tabular-nums"
                    :class="weightColor(marker.weight)"
                  >{{ marker.weight.toFixed(2) }}</span>
                </td>
                <td class="px-4 py-2.5 max-w-[200px] truncate" style="color: var(--text-3);">{{ marker.source_detail || '—' }}</td>
                <td class="px-4 py-2.5" style="color: var(--text-3);">{{ formatDate(marker.added_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Upstream info (if from external source) -->
      <div v-if="entry.upstream_id" class="rounded-xl shadow-sm p-5" style="background: var(--surface); border: 1px solid var(--border);">
        <h2 class="text-[14px] font-semibold mb-3" style="color: var(--text-1);">Upstream Information</h2>
        <div class="grid grid-cols-2 gap-4 text-[12px]">
          <div>
            <span style="color: var(--text-3);">Upstream ID</span>
            <p class="font-mono mt-0.5" style="color: var(--text-2);">{{ entry.upstream_id }}</p>
          </div>
          <div v-if="entry.upstream_version">
            <span style="color: var(--text-3);">Upstream Version</span>
            <p class="font-mono mt-0.5" style="color: var(--text-2);">{{ entry.upstream_version }}</p>
          </div>
        </div>
      </div>

    </template>

    <!-- ── Subscribe modal ─────────────────────────────────────────────────── -->
    <Teleport to="body">
      <div
        v-if="showSubscribeModal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        style="background: rgba(15,20,36,0.5)"
        @click.self="showSubscribeModal = false"
      >
        <div
          class="rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden"
          style="background: var(--surface);"
          role="dialog"
          aria-modal="true"
          aria-label="Subscribe group to library entry"
        >
          <div class="flex items-center justify-between px-5 py-4" style="border-bottom: 1px solid var(--border);">
            <h3 class="text-[15px] font-semibold" style="color: var(--text-1);">Subscribe Group</h3>
            <button
              class="w-7 h-7 flex items-center justify-center rounded-lg transition-colors text-[18px] leading-none"
              style="color: var(--text-3);"
              aria-label="Close dialog"
              @click="showSubscribeModal = false"
            >&times;</button>
          </div>

          <div class="px-5 py-4 space-y-4">
            <div v-if="subscribeError" class="px-3 py-2 text-sm rounded-lg" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
              {{ subscribeError }}
            </div>

            <div>
              <label for="sub-group" class="block text-xs font-medium mb-1" style="color: var(--text-2);">Group ID <span class="text-[var(--error-text)]">*</span></label>
              <input
                id="sub-group"
                v-model="subscribeGroupId"
                type="text"
                placeholder="Enter group ID"
                class="w-full px-3 py-2 text-sm rounded-lg outline-none transition" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              />
            </div>

            <div class="flex items-center gap-2">
              <input
                id="sub-auto"
                v-model="subscribeAutoUpdate"
                type="checkbox"
                class="rounded border-[var(--border)] text-[var(--info-text)] focus:ring-[var(--input-focus)]"
              />
              <label for="sub-auto" class="text-xs" style="color: var(--text-2);">Auto-update when entry changes</label>
            </div>
          </div>

          <div class="px-5 py-3 flex items-center justify-end gap-2" style="background: var(--surface-inset); border-top: 1px solid var(--border);">
            <button
              class="px-4 py-1.5 rounded-lg text-[13px] font-medium transition-colors"
              style="background: var(--surface-hover); color: var(--text-2);"
              @click="showSubscribeModal = false"
            >Cancel</button>
            <button
              class="px-4 py-1.5 rounded-lg bg-[var(--brand-primary)] text-white text-[13px] font-medium hover:opacity-90 transition-colors disabled:opacity-50"
              :disabled="subscribing"
              @click="handleSubscribe"
            >{{ subscribing ? 'Subscribing...' : 'Subscribe' }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── Edit modal ──────────────────────────────────────────────────────── -->
    <Teleport to="body">
      <div
        v-if="showEditModal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        style="background: rgba(15,20,36,0.5)"
        @click.self="showEditModal = false"
      >
        <div
          class="rounded-2xl shadow-2xl w-full max-w-md overflow-hidden"
          style="background: var(--surface);"
          role="dialog"
          aria-modal="true"
          aria-label="Edit library entry"
        >
          <div class="flex items-center justify-between px-5 py-4" style="border-bottom: 1px solid var(--border);">
            <h3 class="text-[15px] font-semibold" style="color: var(--text-1);">Edit Entry</h3>
            <button
              class="w-7 h-7 flex items-center justify-center rounded-lg transition-colors text-[18px] leading-none"
              style="color: var(--text-3);"
              aria-label="Close dialog"
              @click="showEditModal = false"
            >&times;</button>
          </div>

          <div class="px-5 py-4 space-y-4">
            <div v-if="editError" class="px-3 py-2 text-sm rounded-lg" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
              {{ editError }}
            </div>

            <div>
              <label for="edit-name" class="block text-xs font-medium mb-1" style="color: var(--text-2);">Name <span class="text-[var(--error-text)]">*</span></label>
              <input
                id="edit-name"
                v-model="editForm.name"
                type="text"
                class="w-full px-3 py-2 text-sm rounded-lg outline-none transition" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              />
            </div>

            <div>
              <label for="edit-vendor" class="block text-xs font-medium mb-1" style="color: var(--text-2);">Vendor</label>
              <input
                id="edit-vendor"
                v-model="editForm.vendor"
                type="text"
                class="w-full px-3 py-2 text-sm rounded-lg outline-none transition" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              />
            </div>

            <div>
              <label for="edit-category" class="block text-xs font-medium mb-1" style="color: var(--text-2);">Category</label>
              <input
                id="edit-category"
                v-model="editForm.category"
                type="text"
                class="w-full px-3 py-2 text-sm rounded-lg outline-none transition" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              />
            </div>

            <div>
              <label for="edit-desc" class="block text-xs font-medium mb-1" style="color: var(--text-2);">Description</label>
              <textarea
                id="edit-desc"
                v-model="editForm.description"
                rows="2"
                class="w-full px-3 py-2 text-sm rounded-lg outline-none transition resize-none" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              />
            </div>

            <div>
              <label for="edit-tags" class="block text-xs font-medium mb-1" style="color: var(--text-2);">
                Tags <span class="font-normal" style="color: var(--text-3);">(comma-separated)</span>
              </label>
              <input
                id="edit-tags"
                v-model="editForm.tags"
                type="text"
                class="w-full px-3 py-2 text-sm rounded-lg outline-none transition" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              />
            </div>
          </div>

          <div class="px-5 py-3 flex items-center justify-end gap-2" style="background: var(--surface-inset); border-top: 1px solid var(--border);">
            <button
              class="px-4 py-1.5 rounded-lg text-[13px] font-medium transition-colors"
              style="background: var(--surface-hover); color: var(--text-2);"
              @click="showEditModal = false"
            >Cancel</button>
            <button
              class="px-4 py-1.5 rounded-lg bg-[var(--brand-primary)] text-white text-[13px] font-medium hover:opacity-90 transition-colors disabled:opacity-50"
              :disabled="isEditing"
              @click="handleEdit"
            >{{ isEditing ? 'Saving...' : 'Save Changes' }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── Delete confirmation modal ───────────────────────────────────────── -->
    <Teleport to="body">
      <div
        v-if="showDeleteConfirm"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        style="background: rgba(15,20,36,0.5)"
        @click.self="showDeleteConfirm = false"
      >
        <div class="rounded-xl shadow-2xl w-full max-w-sm p-6 text-center" style="background: var(--surface);" role="alertdialog" aria-modal="true" aria-label="Confirm entry deletion">
          <div class="w-12 h-12 rounded-full bg-[var(--error-bg)] flex items-center justify-center mx-auto mb-3">
            <svg class="w-6 h-6 text-[var(--error-text)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </div>
          <h3 class="text-[15px] font-semibold mb-1" style="color: var(--heading);">Delete library entry?</h3>
          <p class="text-[13px] mb-5" style="color: var(--text-3);">This action cannot be undone. All subscriptions to this entry will be removed.</p>
          <div class="flex items-center justify-center gap-2">
            <button
              class="px-4 py-2 rounded-lg text-[13px] font-medium transition-colors"
              style="background: var(--surface-hover); color: var(--text-2);"
              @click="showDeleteConfirm = false"
            >Cancel</button>
            <button
              class="px-4 py-2 rounded-lg bg-[var(--error-text)] text-white text-[13px] font-medium hover:opacity-90 transition-colors disabled:opacity-50"
              :disabled="actionLoading === 'delete'"
              @click="handleDelete"
            >{{ actionLoading === 'delete' ? 'Deleting...' : 'Delete' }}</button>
          </div>
        </div>
      </div>
    </Teleport>

  </div>
</template>
