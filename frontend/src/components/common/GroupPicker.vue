<!--
  GroupPicker — multi-select for groups fetched from the groups API.
  Displays group names with agent counts. Selected groups emit as an array
  of group names (matching the agents.group_name field).
-->
<script setup lang="ts">
/**
 * Multi-select dropdown for groups.
 *
 * @param modelValue - Currently selected group names.
 * @emits update:modelValue - When selection changes.
 */
import { ref, onMounted, computed } from 'vue'
import client from '@/api/client'

interface Group {
  group_id: string
  group_name: string | null
  agent_count: number
  site_name: string
}

const props = defineProps<{
  modelValue: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const groups = ref<Group[]>([])
const loading = ref(false)
const open = ref(false)
const search = ref('')

const filtered = computed(() => {
  const q = search.value.toLowerCase()
  return groups.value.filter(g =>
    (g.group_name ?? '').toLowerCase().includes(q),
  )
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
    const { data } = await client.get<{ groups: Group[] }>('/groups/', {
      params: { limit: 1000 },
    })
    groups.value = data.groups
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
        style="background: var(--scope-group-bg); color: white;"
      >
        {{ name }}
        <button class="hover:opacity-70" @click.stop="remove(name)">&times;</button>
      </span>
      <span v-if="modelValue.length === 0" style="color: var(--text-3);">All groups (no filter)</span>
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
        placeholder="Search groups..."
        @click.stop
      >
      <div v-if="loading" class="p-3 text-xs text-center" style="color: var(--text-3);">Loading groups...</div>
      <div
        v-for="g in filtered"
        :key="g.group_id"
        class="px-3 py-2 text-sm cursor-pointer hover:bg-opacity-50 flex items-center justify-between"
        :style="{ background: isSelected(g.group_name ?? '') ? 'var(--surface-hover)' : '' }"
        @click.stop="toggle(g.group_name ?? '')"
      >
        <div class="flex items-center gap-2">
          <input type="checkbox" :checked="isSelected(g.group_name ?? '')" class="pointer-events-none" tabindex="-1">
          <span style="color: var(--text-1);">{{ g.group_name }}</span>
        </div>
        <span class="text-xs" style="color: var(--text-3);">{{ g.agent_count }} agents</span>
      </div>
      <div v-if="!loading && filtered.length === 0" class="p-3 text-xs text-center" style="color: var(--text-3);">No groups found</div>
    </div>

    <!-- Click-outside close -->
    <div v-if="open" class="fixed inset-0 z-10" @click="open = false"></div>
  </div>
</template>
