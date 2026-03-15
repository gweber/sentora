<!--
  TaxonomyCategoryPicker — dropdown for selecting a taxonomy category.
  Fetches categories from the taxonomy API and shows them with entry counts.
-->
<script setup lang="ts">
/**
 * Single-select dropdown for taxonomy categories.
 *
 * @param modelValue - Currently selected category key.
 * @emits update:modelValue - When selection changes.
 */
import { ref, onMounted, computed } from 'vue'
import { useTaxonomyStore } from '@/stores/useTaxonomyStore'

const props = defineProps<{
  modelValue: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const store = useTaxonomyStore()
const open = ref(false)
const search = ref('')

const filtered = computed(() => {
  const q = search.value.toLowerCase()
  return store.categories.filter(c =>
    c.display.toLowerCase().includes(q) || c.key.toLowerCase().includes(q),
  )
})

const selectedDisplay = computed(() => {
  if (!props.modelValue) return ''
  const cat = store.categories.find(c => c.key === props.modelValue)
  return cat ? cat.display : props.modelValue
})

function select(key: string) {
  emit('update:modelValue', key)
  open.value = false
}

onMounted(async () => {
  if (store.categories.length === 0) {
    await store.fetchCategories()
  }
})
</script>

<template>
  <div class="relative">
    <!-- Selected display -->
    <div
      class="min-h-[38px] w-full px-3 py-1.5 rounded-lg text-sm flex items-center cursor-pointer"
      style="background: var(--surface-inset); border: 1px solid var(--border); color: var(--text-1);"
      @click="open = !open"
    >
      <span v-if="modelValue" style="color: var(--text-1);">{{ selectedDisplay }}</span>
      <span v-else style="color: var(--text-3);">Select taxonomy category...</span>
      <svg class="w-4 h-4 ml-auto" style="color: var(--text-3);" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </div>

    <!-- Dropdown -->
    <div
      v-if="open"
      class="absolute z-20 mt-1 w-full rounded-lg shadow-lg max-h-60 overflow-y-auto"
      style="background: var(--surface); border: 1px solid var(--border);"
    >
      <input
        v-model="search"
        class="w-full px-3 py-2 text-sm sticky top-0"
        style="background: var(--surface-inset); border-bottom: 1px solid var(--border); color: var(--text-1);"
        placeholder="Search categories..."
        @click.stop
      >
      <div v-if="store.isLoading" class="p-3 text-xs text-center" style="color: var(--text-3);">Loading categories...</div>
      <div
        v-for="cat in filtered"
        :key="cat.key"
        class="px-3 py-2 text-sm cursor-pointer flex items-center justify-between"
        :style="{ background: modelValue === cat.key ? 'var(--surface-hover)' : '' }"
        @click.stop="select(cat.key)"
      >
        <span style="color: var(--text-1);">{{ cat.display }}</span>
        <span class="text-xs" style="color: var(--text-3);">{{ cat.entry_count }} entries</span>
      </div>
      <div v-if="!store.isLoading && filtered.length === 0" class="p-3 text-xs text-center" style="color: var(--text-3);">No categories found</div>
    </div>

    <!-- Click-outside close -->
    <div v-if="open" class="fixed inset-0 z-10" @click="open = false"></div>
  </div>
</template>
