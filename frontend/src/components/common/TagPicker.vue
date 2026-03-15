<!--
  TagPicker — multi-select for S1 tags fetched from the sync/tags API.
  Selected tags emit as an array of tag name strings (matching s1_agents.tags field).
-->
<script setup lang="ts">
/**
 * Multi-select dropdown for SentinelOne tags.
 *
 * @param modelValue - Currently selected tag names.
 * @emits update:modelValue - When selection changes.
 */
import { ref, onMounted, computed } from 'vue'
import { listSyncedTags } from '@/api/tags'

interface TagItem {
  name: string
  scope: string
}

const props = defineProps<{
  modelValue: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const tags = ref<TagItem[]>([])
const loading = ref(false)
const open = ref(false)
const search = ref('')

const filtered = computed(() => {
  const q = search.value.toLowerCase()
  return tags.value.filter(t => t.name.toLowerCase().includes(q))
})

function isSelected(name: string): boolean {
  return props.modelValue.includes(name)
}

function toggle(name: string) {
  const current = [...props.modelValue]
  const idx = current.indexOf(name)
  if (idx >= 0) {
    current.splice(idx, 1)
  } else {
    current.push(name)
  }
  emit('update:modelValue', current)
}

function remove(name: string) {
  emit('update:modelValue', props.modelValue.filter(n => n !== name))
}

onMounted(async () => {
  loading.value = true
  try {
    const resp = await listSyncedTags()
    tags.value = resp.tags.map(t => ({ name: t.name, scope: t.scope }))
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="relative">
    <!-- Selected tags display -->
    <div
      class="min-h-[38px] w-full px-3 py-1.5 rounded-lg text-sm flex flex-wrap gap-1 items-center cursor-pointer"
      style="background: var(--surface-inset); border: 1px solid var(--border); color: var(--text-1);"
      @click="open = !open"
    >
      <span
        v-for="name in modelValue"
        :key="name"
        class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs"
        style="background: var(--accent-bg); color: var(--accent-text);"
      >
        {{ name }}
        <button class="hover:opacity-70" @click.stop="remove(name)">&times;</button>
      </span>
      <span v-if="modelValue.length === 0" style="color: var(--text-3);">All tags (no filter)</span>
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
        placeholder="Search tags..."
        @click.stop
      >
      <div v-if="loading" class="p-3 text-xs text-center" style="color: var(--text-3);">Loading tags...</div>
      <div
        v-for="t in filtered"
        :key="t.name"
        class="px-3 py-2 text-sm cursor-pointer hover:bg-opacity-50 flex items-center justify-between"
        :style="{ background: isSelected(t.name) ? 'var(--surface-hover)' : '' }"
        @click.stop="toggle(t.name)"
      >
        <div class="flex items-center gap-2">
          <input type="checkbox" :checked="isSelected(t.name)" class="pointer-events-none" tabindex="-1">
          <span style="color: var(--text-1);">{{ t.name }}</span>
        </div>
        <span class="text-xs" style="color: var(--text-3);">{{ t.scope }}</span>
      </div>
      <div v-if="!loading && filtered.length === 0" class="p-3 text-xs text-center" style="color: var(--text-3);">No tags found</div>
    </div>

    <!-- Click-outside close -->
    <div v-if="open" class="fixed inset-0 z-10" @click="open = false"></div>
  </div>
</template>
