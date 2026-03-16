<!--
  Shared taxonomy category sidebar with full CRUD.
  Used by TaxonomyView (select mode) and TagEditorView (expand mode with entries).
-->
<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useTaxonomyStore } from '@/stores/useTaxonomyStore'
import type { CategorySummary, SoftwareEntry } from '@/types/taxonomy'

const props = withDefaults(defineProps<{
  /** Header label shown in uppercase at the top */
  title?: string
  /** Which category key is currently active (highlighted) */
  activeKey?: string | null
  /** Show search input */
  searchable?: boolean
  /** Show entries inline under expanded category (for drag sources) */
  expandable?: boolean
  /** Hide create/edit/delete buttons (category CRUD managed elsewhere) */
  readonly?: boolean
}>(), {
  title: 'Categories',
  activeKey: null,
  searchable: false,
  expandable: false,
  readonly: false,
})

const emit = defineEmits<{
  select: [cat: CategorySummary]
  'entry-click': [entry: SoftwareEntry]
  'entry-dragstart': [event: DragEvent, entry: SoftwareEntry]
}>()

const taxStore = useTaxonomyStore()

// ── Search ───────────────────────────────────────────────────────────────────
const searchQuery = ref('')
const filteredCategories = computed(() => {
  if (!searchQuery.value.trim()) return taxStore.categories
  const q = searchQuery.value.toLowerCase()
  return taxStore.categories.filter(c => c.display.toLowerCase().includes(q))
})

// ── Expand mode state ────────────────────────────────────────────────────────
const expandedKey = ref<string | null>(null)

async function handleCategoryClick(cat: CategorySummary) {
  if (props.expandable) {
    // Toggle expand/collapse
    if (expandedKey.value === cat.key) {
      expandedKey.value = null
    } else {
      expandedKey.value = cat.key
      await taxStore.fetchEntriesByCategory(cat.key)
    }
  }
  emit('select', cat)
}

/** The key used for highlighting — either explicit activeKey or internal expandedKey */
const effectiveActiveKey = computed(() => {
  if (props.expandable) return expandedKey.value
  return props.activeKey
})

// ── Category CRUD state ──────────────────────────────────────────────────────
const showCatModal = ref(false)
const editingCategory = ref<CategorySummary | null>(null)
const isNewCategory = ref(false)
const catForm = reactive({ key: '', display: '' })
const catSaving = ref(false)
const catDeleteConfirmKey = ref<string | null>(null)
const catDeleting = ref(false)

function openNewCategory() {
  editingCategory.value = null
  isNewCategory.value = true
  catForm.key = ''
  catForm.display = ''
  showCatModal.value = true
}

function openEditCategory(cat: CategorySummary, e: Event) {
  e.stopPropagation()
  editingCategory.value = cat
  isNewCategory.value = false
  catForm.key = cat.key
  catForm.display = cat.display
  showCatModal.value = true
}

async function saveCategory() {
  catSaving.value = true
  try {
    if (isNewCategory.value) {
      const cat = await taxStore.createCategory({
        key: catForm.key.trim(),
        display: catForm.display.trim(),
      })
      if (cat) emit('select', cat)
      showCatModal.value = false
      return
    }

    if (!editingCategory.value) return
    const payload: Record<string, string> = {}
    if (catForm.key !== editingCategory.value.key) payload.key = catForm.key
    if (catForm.display !== editingCategory.value.display) payload.display = catForm.display
    if (Object.keys(payload).length === 0) { showCatModal.value = false; return }

    const ok = await taxStore.updateCategory(editingCategory.value.key, payload)
    if (ok) {
      const newKey = payload.key ?? editingCategory.value.key
      const updated = taxStore.categories.find(c => c.key === newKey)
      if (updated) emit('select', updated)
      showCatModal.value = false
    }
  } finally {
    catSaving.value = false
  }
}

async function doDeleteCategory(cat: CategorySummary, e: Event) {
  e.stopPropagation()
  catDeleting.value = true
  try {
    const ok = await taxStore.deleteCategory(cat.key)
    if (ok) {
      catDeleteConfirmKey.value = null
      if (effectiveActiveKey.value === cat.key) {
        expandedKey.value = null
        const first = taxStore.categories[0]
        if (first) emit('select', first)
      }
    }
  } finally {
    catDeleting.value = false
  }
}
</script>

<template>
  <aside class="w-[240px] shrink-0 flex flex-col overflow-hidden" style="border-right: 1px solid var(--border); background: var(--surface-alt);">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 shrink-0" style="border-bottom: 1px solid var(--border);">
      <p class="text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">{{ title }}</p>
      <button
        v-if="!readonly"
        title="New category"
        class="p-1 rounded-md transition-colors" style="color: var(--text-3);"
        @click="openNewCategory"
      >
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4" />
        </svg>
      </button>
    </div>

    <!-- Search -->
    <div v-if="searchable" class="px-3 pt-2 pb-1 shrink-0">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search categories…"
        class="w-full text-[13px] px-2.5 py-1.5 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-400"
        style="border: 1px solid var(--input-border); background: var(--surface); color: var(--text-1);"
      />
    </div>

    <!-- Loading -->
    <div
      v-if="taxStore.isLoading && taxStore.categories.length === 0"
      class="p-4 text-[13px]" style="color: var(--text-3);"
    >
      Loading…
    </div>

    <!-- Category list -->
    <nav class="flex-1 overflow-y-auto p-2 space-y-0.5">
      <div
        v-for="cat in filteredCategories"
        :key="cat.key"
      >
        <div
          class="group relative flex items-center rounded-md transition-colors"
          :class="effectiveActiveKey === cat.key
            ? 'bg-indigo-600 text-white'
            : ''"
          :style="effectiveActiveKey !== cat.key ? 'color: var(--text-2);' : ''"
        >
          <!-- Main clickable area -->
          <button
            class="flex-1 flex items-center justify-between px-3 py-2 text-left min-w-0"
            @click="handleCategoryClick(cat)"
          >
            <span class="text-[13px] font-medium truncate">{{ cat.display }}</span>
            <div class="flex items-center gap-1.5 shrink-0">
              <span
                v-if="!expandable || expandedKey !== cat.key"
                class="text-[11px] font-medium px-1.5 py-0.5 rounded-full"
                :class="effectiveActiveKey === cat.key
                  ? 'bg-white/20 text-white'
                  : ''"
                :style="effectiveActiveKey !== cat.key ? 'background: var(--surface-hover); color: var(--text-3);' : ''"
              >
                {{ cat.entry_count }}
              </span>
              <!-- Chevron for expandable mode -->
              <svg
                v-if="expandable"
                class="w-3.5 h-3.5 transition-transform"
                :class="{ 'rotate-90': expandedKey === cat.key }"
                fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"
              >
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </div>
          </button>

          <!-- Hover actions (overlay on right side) -->
          <div
            v-if="!readonly"
            class="absolute right-0 top-0 bottom-0 hidden group-hover:flex items-center gap-0.5 pr-1.5 rounded-r-md"
            :class="effectiveActiveKey === cat.key
              ? 'bg-indigo-600 text-white'
              : ''"
            :style="effectiveActiveKey !== cat.key ? 'background: var(--surface-hover); color: var(--text-3);' : ''"
          >
            <!-- Edit category -->
            <button
              title="Rename category"
              class="p-1 rounded transition-colors hover:bg-black/10"
              @click="openEditCategory(cat, $event)"
            >
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>

            <!-- Delete category -->
            <template v-if="catDeleteConfirmKey === cat.key">
              <button
                :disabled="catDeleting"
                class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                @click="doDeleteCategory(cat, $event)"
              >{{ catDeleting ? '…' : 'Del' }}</button>
              <button
                class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-black/10 hover:bg-black/20"
                @click.stop="catDeleteConfirmKey = null"
              >✕</button>
            </template>
            <button
              v-else
              title="Delete category"
              class="p-1 rounded transition-colors hover:bg-red-500/20 hover:text-red-400"
              @click.stop="catDeleteConfirmKey = cat.key"
            >
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>

        <!-- Expanded entries (expandable mode only) -->
        <div
          v-if="expandable && expandedKey === cat.key"
          class="ml-3 mt-0.5 mb-1 border-l-2 border-indigo-200"
        >
          <div
            v-for="entry in taxStore.entriesByCategory[cat.key] ?? []"
            :key="entry.id"
            class="flex items-center gap-1.5 px-3 py-1.5 cursor-grab hover:bg-indigo-50 group/entry rounded-r-md"
            draggable="true"
            @dragstart="emit('entry-dragstart', $event, entry)"
            @dblclick="emit('entry-click', entry)"
          >
            <svg class="w-3 h-3 shrink-0 group-hover/entry:text-indigo-400" style="color: var(--text-3);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            <span class="text-[13px] truncate" style="color: var(--text-2);">{{ entry.name }}</span>
          </div>
          <p
            v-if="!(taxStore.entriesByCategory[cat.key]?.length)"
            class="text-[11px] px-3 py-2" style="color: var(--text-3);"
          >
            No entries
          </p>
        </div>
      </div>
    </nav>

    <!-- Category create/rename modal -->
    <Teleport to="body">
      <div
        v-if="showCatModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
        @mousedown.self="showCatModal = false"
      >
        <div class="rounded-2xl shadow-2xl w-full max-w-sm" style="background: var(--surface);">
          <div class="flex items-center justify-between px-6 py-4" style="border-bottom: 1px solid var(--border-light);">
            <h3 class="text-[15px] font-semibold" style="color: var(--heading);">
              {{ isNewCategory ? 'New category' : 'Rename category' }}
            </h3>
            <button
              class="p-1.5 rounded-lg transition-colors" style="color: var(--text-3);"
              @click="showCatModal = false"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <form class="px-6 py-5 space-y-4" @submit.prevent="saveCategory">
            <div>
              <label class="block text-[12px] font-medium mb-1" style="color: var(--text-2);">Category key</label>
              <input
                v-model="catForm.key"
                required
                placeholder="e.g. scada_hmi"
                class="w-full rounded-lg px-3 py-2 text-[13px] font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
              />
              <p v-if="!isNewCategory" class="mt-1 text-[11px]" style="color: var(--text-3);">Changing the key updates all entries in this category.</p>
            </div>

            <div>
              <label class="block text-[12px] font-medium mb-1" style="color: var(--text-2);">Display label</label>
              <input
                v-model="catForm.display"
                required
                placeholder="e.g. SCADA / HMI"
                class="w-full rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
              />
            </div>

            <p v-if="isNewCategory" class="text-[11px]" style="color: var(--text-3);">
              The category will be created empty. Add entries to it afterwards.
            </p>

            <p v-if="taxStore.error" class="text-[12px] text-red-600">{{ taxStore.error }}</p>

            <div class="flex justify-end gap-2 pt-1">
              <button
                type="button"
                class="px-4 py-2 rounded-lg text-[13px] font-medium transition-colors" style="color: var(--text-2); background: var(--surface-hover);"
                @click="showCatModal = false"
              >Cancel</button>
              <button
                type="submit"
                :disabled="catSaving"
                class="px-4 py-2 rounded-lg text-[13px] font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >{{ catSaving ? 'Saving…' : (isNewCategory ? 'Create' : 'Save') }}</button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>
  </aside>
</template>
