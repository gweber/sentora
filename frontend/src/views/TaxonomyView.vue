<!--
  Taxonomy view — full CRUD for the software catalog.
  Left: category sidebar with create/rename/delete.
  Right: entries with add/edit/delete actions + inline pattern preview.
-->
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useTaxonomyStore } from '@/stores/useTaxonomyStore'
import * as taxonomyApi from '@/api/taxonomy'
import type { CategorySummary, PatternPreviewResponse, SoftwareEntry, SoftwareEntryCreateRequest } from '@/types/taxonomy'
import CategorySidebar from '@/components/common/CategorySidebar.vue'

// ── Category management state ─────────────────────────────────────────────────

const taxStore = useTaxonomyStore()
const selectedCategory = ref<CategorySummary | null>(null)

// ── Modal state ───────────────────────────────────────────────────────────────
const showModal = ref(false)
const editingEntry = ref<SoftwareEntry | null>(null)
const saving = ref(false)
const saveError = ref<string | null>(null)
const deleteError = ref<string | null>(null)
const deleteConfirmId = ref<string | null>(null)
const deleting = ref(false)

const form = reactive({
  name: '',
  patterns: '',        // newline-separated in the textarea
  publisher: '',
  category: '',
  category_display: '',
  subcategory: '',
  industry: '',        // comma-separated in the input
  description: '',
  is_universal: false,
})

// ── Pattern preview state (per-entry, all patterns at once) ──────────────────
const previewEntryId = ref<string | null>(null)
const previewLoading = ref(false)
const previewData = ref<PatternPreviewResponse | null>(null)

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(async () => {
  await taxStore.fetchCategories()
  const first = taxStore.categories[0]
  if (first) await onCategorySelected(first)
})

// ── Open modal ────────────────────────────────────────────────────────────────

function openAdd() {
  editingEntry.value = null
  Object.assign(form, {
    name: '',
    patterns: '',
    publisher: '',
    category: selectedCategory.value?.key ?? '',
    category_display: selectedCategory.value?.display ?? '',
    subcategory: '',
    industry: '',
    description: '',
    is_universal: false,
  })
  showModal.value = true
}

function openEdit(entry: SoftwareEntry) {
  editingEntry.value = entry
  Object.assign(form, {
    name: entry.name,
    patterns: entry.patterns.join('\n'),
    publisher: entry.publisher ?? '',
    category: entry.category,
    category_display: entry.category_display,
    subcategory: entry.subcategory ?? '',
    industry: entry.industry.join(', '),
    description: entry.description ?? '',
    is_universal: entry.is_universal,
  })
  showModal.value = true
}

// ── Save (create or update) ───────────────────────────────────────────────────

async function save() {
  saving.value = true
  saveError.value = null
  try {
    const payload: SoftwareEntryCreateRequest = {
      name: form.name.trim(),
      patterns: form.patterns.split('\n').map(p => p.trim()).filter(Boolean),
      publisher: form.publisher.trim() || null,
      category: form.category.trim(),
      category_display: form.category_display.trim(),
      subcategory: form.subcategory.trim() || null,
      industry: form.industry.split(',').map(i => i.trim()).filter(Boolean),
      description: form.description.trim() || null,
      is_universal: form.is_universal,
    }

    if (editingEntry.value) {
      await taxStore.editEntry(editingEntry.value.id, payload, editingEntry.value.category)
      if (editingEntry.value.category !== form.category) {
        await taxStore.fetchEntriesByCategory(editingEntry.value.category, true)
      }
    } else {
      await taxStore.addEntry(payload)
    }

    await taxStore.fetchEntriesByCategory(form.category, true)
    await taxStore.fetchCategories()

    const updated = taxStore.categories.find(c => c.key === selectedCategory.value?.key)
    if (updated) selectedCategory.value = updated

    showModal.value = false
  } catch (e) {
    saveError.value = e instanceof Error ? e.message : 'Failed to save entry'
  } finally {
    saving.value = false
  }
}

// ── Delete ────────────────────────────────────────────────────────────────────

async function doDelete(entry: SoftwareEntry) {
  deleting.value = true
  deleteError.value = null
  try {
    await taxStore.deleteEntry(entry.id, entry.category)
    await taxStore.fetchEntriesByCategory(entry.category, true)
    const updated = taxStore.categories.find(c => c.key === selectedCategory.value?.key)
    if (updated) selectedCategory.value = updated
  } catch (e) {
    deleteError.value = e instanceof Error ? e.message : 'Failed to delete entry'
  } finally {
    deleting.value = false
    deleteConfirmId.value = null
  }
}

// ── Toggle universal ──────────────────────────────────────────────────────────

async function handleToggleUniversal(entry: SoftwareEntry) {
  await taxStore.toggleUniversal(entry.id, entry.category)
  if (selectedCategory.value) {
    await taxStore.fetchEntriesByCategory(selectedCategory.value.key, true)
  }
}

// ── Pattern preview (per-entry, all patterns at once) ────────────────────────

async function toggleEntryPreview(entry: SoftwareEntry) {
  if (previewEntryId.value === entry.id) {
    previewEntryId.value = null
    previewData.value = null
    return
  }
  previewEntryId.value = entry.id
  previewLoading.value = true
  previewData.value = null
  try {
    previewData.value = await taxonomyApi.previewPattern({ patterns: entry.patterns })
  } catch {
    previewData.value = null
  } finally {
    previewLoading.value = false
  }
}

// ── Category selection from sidebar ───────────────────────────────────────────

async function onCategorySelected(cat: CategorySummary) {
  selectedCategory.value = cat
  previewEntryId.value = null
  previewData.value = null
  await taxStore.fetchEntriesByCategory(cat.key)
}
</script>

<template>
  <div class="flex h-full overflow-hidden">

    <!-- ── Left: Category sidebar ─────────────────────────────────────────── -->
    <CategorySidebar
      title="Categories"
      searchable
      :active-key="selectedCategory?.key ?? null"
      @select="onCategorySelected"
    />

    <!-- ── Right: Entries ─────────────────────────────────────────────────── -->
    <main class="flex-1 overflow-y-auto p-6">

      <div v-if="!selectedCategory"
        class="flex items-center justify-center h-full text-[13px]" style="color: var(--text-3);">
        Select a category to see entries.
      </div>

      <template v-else>
        <!-- Header -->
        <div class="flex items-center justify-between mb-5">
          <div>
            <h2 class="text-[15px] font-semibold" style="color: var(--heading);">{{ selectedCategory.display }}</h2>
            <p class="text-[12px] mt-0.5" style="color: var(--text-3);">{{ selectedCategory.entry_count }} entries</p>
          </div>
          <button
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--brand-primary)] text-white text-[13px] font-medium hover:bg-[var(--brand-primary-dark)] transition-colors"
            @click="openAdd"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4" />
            </svg>
            Add entry
          </button>
        </div>

        <div v-if="deleteError" class="text-[12px] font-medium text-[var(--error-text)] mb-3 px-1">{{ deleteError }}</div>

        <div v-if="taxStore.isLoading" class="text-[13px] py-10 text-center" style="color: var(--text-3);">
          Loading…
        </div>

        <div
          v-else-if="!taxStore.entriesByCategory[selectedCategory.key]?.length"
          class="text-[13px] py-10 text-center" style="color: var(--text-3);"
        >
          No entries in this category.
        </div>

        <!-- Entry cards -->
        <div v-else class="grid gap-2">
          <div
            v-for="entry in taxStore.entriesByCategory[selectedCategory.key]"
            :key="entry.id"
            class="rounded-xl px-4 py-3 transition-colors"
            style="background: var(--surface); border: 1px solid var(--border);"
          >
            <div class="flex items-start justify-between gap-3">
              <!-- Left: content -->
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2 mb-1.5 flex-wrap">
                  <span class="text-[13px] font-semibold" style="color: var(--heading);">{{ entry.name }}</span>
                  <span v-if="entry.publisher" class="text-[11px]" style="color: var(--text-3);">{{ entry.publisher }}</span>
                  <span
                    v-if="entry.is_universal"
                    class="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-[var(--brand-primary-light)] text-[var(--brand-primary)] border border-[var(--brand-primary-light)]"
                  >
                    Universal
                  </span>
                  <span
                    v-if="entry.user_added"
                    class="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-[var(--warn-bg)] text-[var(--warn-text)] border border-[var(--warn-border)]"
                  >
                    Custom
                  </span>
                </div>

                <!-- Pattern pills -->
                <div class="flex flex-wrap gap-1.5">
                  <span
                    v-for="p in entry.patterns"
                    :key="p"
                    class="text-[11px] font-mono rounded px-2 py-0.5"
                    style="background: var(--surface-inset); border: 1px solid var(--border); color: var(--text-2);"
                  >{{ p }}</span>
                </div>

                <!-- Inline preview panel (per entry, all patterns) -->
                <div
                  v-if="previewEntryId === entry.id"
                  class="mt-2 rounded-lg border border-[var(--brand-primary-light)] bg-[var(--brand-primary-light)] p-3"
                >
                  <!-- Loading -->
                  <div v-if="previewLoading" class="text-[11px] text-[var(--brand-primary)] flex items-center gap-1.5">
                    <svg class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                    </svg>
                    Matching patterns against installed apps…
                  </div>

                  <!-- No matches -->
                  <div v-else-if="!previewData || previewData.total_apps === 0" class="text-[11px] italic" style="color: var(--text-3);">
                    No installed apps match these patterns.
                  </div>

                  <!-- Results -->
                  <template v-else>
                    <!-- Stats row -->
                    <div class="flex items-center gap-3 mb-2.5">
                      <span class="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-[var(--brand-primary-light)] text-[var(--brand-primary)]">
                        {{ previewData.total_apps }} app{{ previewData.total_apps !== 1 ? 's' : '' }}
                      </span>
                      <span class="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-[var(--success-bg)] text-[var(--success-text)]">
                        {{ previewData.total_agents }} agent{{ previewData.total_agents !== 1 ? 's' : '' }}
                      </span>
                    </div>

                    <!-- Matched apps table -->
                    <div class="overflow-y-auto max-h-[180px] mb-2">
                      <table class="w-full text-[11px]">
                        <thead class="bg-[var(--brand-primary-light)] sticky top-0">
                          <tr>
                            <th scope="col" class="text-left px-2 py-1 font-semibold text-[var(--brand-primary)]">App Name</th>
                            <th scope="col" class="text-left px-2 py-1 font-semibold text-[var(--brand-primary)]">Publisher</th>
                            <th scope="col" class="text-right px-2 py-1 font-semibold text-[var(--brand-primary)]">Agents</th>
                          </tr>
                        </thead>
                        <tbody class="divide-y divide-[var(--brand-primary-light)]">
                          <tr v-for="m in previewData.app_matches" :key="m.normalized_name" class="hover:bg-[var(--brand-primary-light)]">
                            <td class="px-2 py-1 font-medium" style="color: var(--text-2);">{{ m.display_name }}</td>
                            <td class="px-2 py-1" style="color: var(--text-3);">{{ m.publisher || '—' }}</td>
                            <td class="px-2 py-1 text-right font-mono" style="color: var(--text-2);">{{ m.agent_count }}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    <!-- Group breakdown -->
                    <div v-if="previewData.group_counts.length > 0">
                      <p class="text-[10px] font-semibold text-[var(--brand-primary)] uppercase tracking-wide mb-1">By Group</p>
                      <div class="flex flex-wrap gap-1.5">
                        <span
                          v-for="g in previewData.group_counts"
                          :key="g.group_name"
                          class="text-[10px] px-1.5 py-0.5 rounded border border-[var(--brand-primary-light)]" style="background: var(--surface); color: var(--text-2);"
                        >
                          {{ g.group_name }} <span class="font-semibold text-[var(--brand-primary)]">{{ g.agent_count }}</span>
                        </span>
                      </div>
                    </div>
                  </template>
                </div>

                <p v-if="entry.description" class="text-[12px] mt-1.5" style="color: var(--text-3);">
                  {{ entry.description }}
                </p>
              </div>

              <!-- Right: action buttons -->
              <div class="flex items-center gap-1 shrink-0 pt-0.5">
                <!-- Preview matches -->
                <button
                  class="p-1.5 rounded-md transition-colors"
                  :class="previewEntryId === entry.id
                    ? 'bg-[var(--brand-primary-light)] text-[var(--brand-primary)]'
                    : ''"
                  :style="previewEntryId === entry.id ? '' : 'color: var(--text-3);'"
                  :title="previewEntryId === entry.id ? 'Hide preview' : 'Preview matches'"
                  @click="toggleEntryPreview(entry)"
                >
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                </button>

                <!-- Toggle universal -->
                <button
                  :title="entry.is_universal ? 'Remove universal flag' : 'Mark as universal'"
                  class="p-1.5 rounded-md transition-colors"
                  :class="entry.is_universal
                    ? 'bg-[var(--brand-primary-light)] text-[var(--brand-primary)] hover:bg-[var(--brand-primary-light)]'
                    : ''"
                  :style="entry.is_universal ? '' : 'color: var(--text-3);'"
                  @click="handleToggleUniversal(entry)"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064" />
                  </svg>
                </button>

                <!-- Edit -->
                <button
                  title="Edit entry"
                  class="p-1.5 rounded-md transition-colors"
                  style="color: var(--text-3);"
                  @click="openEdit(entry)"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>

                <!-- Delete with inline confirm -->
                <template v-if="deleteConfirmId === entry.id">
                  <span class="text-[11px] text-[var(--error-text)] font-medium">Delete?</span>
                  <button
                    :disabled="deleting"
                    class="px-2 py-1 rounded text-[11px] font-medium bg-[var(--error-text)] text-white hover:bg-[var(--error-text)] disabled:opacity-50 transition-colors"
                    @click="doDelete(entry)"
                  >{{ deleting ? '…' : 'Yes' }}</button>
                  <button
                    class="px-2 py-1 rounded text-[11px] font-medium transition-colors"
                    style="background: var(--badge-bg); color: var(--text-2);"
                    @click="deleteConfirmId = null"
                  >No</button>
                </template>
                <button
                  v-else
                  title="Delete entry"
                  class="p-1.5 rounded-md hover:bg-[var(--error-bg)] hover:text-[var(--error-text)] transition-colors"
                  style="color: var(--text-3);"
                  @click="deleteConfirmId = entry.id"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </template>
    </main>

    <!-- ── Modal: Create / Edit entry ──────────────────────────────────────── -->
    <Teleport to="body">
      <div
        v-if="showModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
        @mousedown.self="showModal = false"
      >
        <div class="rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" style="background: var(--surface);" role="dialog" aria-modal="true" :aria-label="editingEntry ? 'Edit taxonomy entry' : 'Add taxonomy entry'">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4" style="border-bottom: 1px solid var(--border-light);">
            <h3 class="text-[15px] font-semibold" style="color: var(--heading);">
              {{ editingEntry ? 'Edit entry' : 'Add entry' }}
            </h3>
            <button
              class="p-1.5 rounded-lg transition-colors"
              style="color: var(--text-3);"
              aria-label="Close dialog"
              @click="showModal = false"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Form -->
          <form class="px-6 py-5 space-y-4" @submit.prevent="save">

            <div>
              <label class="block text-[12px] font-medium mb-1" style="color: var(--text-2);">
                Name <span class="text-[var(--error-text)]">*</span>
              </label>
              <input
                v-model="form.name"
                required
                placeholder="e.g. Siemens WinCC"
                class="w-full rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary)] focus:border-transparent"
                style="border: 1px solid var(--input-border); background: var(--surface); color: var(--text-1);"
              />
            </div>

            <div>
              <label class="block text-[12px] font-medium mb-1" style="color: var(--text-2);">
                Patterns <span class="text-[var(--error-text)]">*</span>
                <span class="font-normal ml-1" style="color: var(--text-3);">(one per line, glob syntax)</span>
              </label>
              <textarea
                v-model="form.patterns"
                required
                rows="3"
                placeholder="wincc*&#10;siemens wincc*"
                class="w-full rounded-lg px-3 py-2 text-[13px] font-mono focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary)] focus:border-transparent resize-none"
                style="border: 1px solid var(--input-border); background: var(--surface); color: var(--text-1);"
              />
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-[12px] font-medium mb-1" style="color: var(--text-2);">
                  Category key <span class="text-[var(--error-text)]">*</span>
                </label>
                <input
                  v-model="form.category"
                  required
                  placeholder="e.g. scada_hmi"
                  class="w-full rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary)] focus:border-transparent"
                  style="border: 1px solid var(--input-border); background: var(--surface); color: var(--text-1);"
                />
              </div>
              <div>
                <label class="block text-[12px] font-medium mb-1" style="color: var(--text-2);">Category label</label>
                <input
                  v-model="form.category_display"
                  placeholder="e.g. SCADA / HMI"
                  class="w-full rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary)] focus:border-transparent"
                  style="border: 1px solid var(--input-border); background: var(--surface); color: var(--text-1);"
                />
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-[12px] font-medium mb-1" style="color: var(--text-2);">Publisher</label>
                <input
                  v-model="form.publisher"
                  placeholder="e.g. Siemens AG"
                  class="w-full rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary)] focus:border-transparent"
                  style="border: 1px solid var(--input-border); background: var(--surface); color: var(--text-1);"
                />
              </div>
              <div>
                <label class="block text-[12px] font-medium mb-1" style="color: var(--text-2);">Subcategory</label>
                <input
                  v-model="form.subcategory"
                  placeholder="optional"
                  class="w-full rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary)] focus:border-transparent"
                  style="border: 1px solid var(--input-border); background: var(--surface); color: var(--text-1);"
                />
              </div>
            </div>

            <div>
              <label class="block text-[12px] font-medium mb-1" style="color: var(--text-2);">
                Industry
                <span class="font-normal ml-1" style="color: var(--text-3);">(comma-separated)</span>
              </label>
              <input
                v-model="form.industry"
                placeholder="e.g. manufacturing, water_treatment"
                class="w-full rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary)] focus:border-transparent"
                style="border: 1px solid var(--input-border); background: var(--surface); color: var(--text-1);"
              />
            </div>

            <div>
              <label class="block text-[12px] font-medium mb-1" style="color: var(--text-2);">Description</label>
              <textarea
                v-model="form.description"
                rows="2"
                placeholder="Optional description…"
                class="w-full rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary)] focus:border-transparent resize-none"
                style="border: 1px solid var(--input-border); background: var(--surface); color: var(--text-1);"
              />
            </div>

            <label class="flex items-center gap-3 cursor-pointer select-none">
              <input
                v-model="form.is_universal"
                type="checkbox"
                class="w-4 h-4 rounded border-gray-300 text-[var(--brand-primary)] focus:ring-[var(--brand-primary)]"
              />
              <span class="text-[13px]" style="color: var(--text-2);">
                Universal
                <span class="font-normal" style="color: var(--text-3);">— exclude from fingerprint suggestions</span>
              </span>
            </label>

            <p v-if="saveError" class="text-[12px] text-[var(--error-text)]">{{ saveError }}</p>
            <p v-if="taxStore.error" class="text-[12px] text-[var(--error-text)]">{{ taxStore.error }}</p>

            <div class="flex justify-end gap-2 pt-1">
              <button
                type="button"
                class="px-4 py-2 rounded-lg text-[13px] font-medium transition-colors"
                style="background: var(--badge-bg); color: var(--text-2);"
                @click="showModal = false"
              >
                Cancel
              </button>
              <button
                type="submit"
                :disabled="saving"
                class="px-4 py-2 rounded-lg text-[13px] font-medium text-white bg-[var(--brand-primary)] hover:bg-[var(--brand-primary-dark)] disabled:opacity-50 transition-colors"
              >
                {{ saving ? 'Saving…' : (editingEntry ? 'Save changes' : 'Add entry') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

  </div>
</template>
