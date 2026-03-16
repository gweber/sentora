<!--
  Anomalies view — list of misclassified and ambiguous agents.
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useClassificationStore } from '@/stores/useClassificationStore'
import type { ClassificationVerdict } from '@/types/classification'
import { formatRelativeTime } from '@/utils/formatters'

const classStore = useClassificationStore()
const filterType = ref<ClassificationVerdict | ''>('')
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    await classStore.fetchResults({
      classification: filterType.value || undefined,
      limit: 100,
    })
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load anomalies'
  }
})

async function applyFilter(type: ClassificationVerdict | '') {
  filterType.value = type
  error.value = null
  try {
    await classStore.fetchResults({ classification: type || undefined, limit: 100 })
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load anomalies'
  }
}

async function acknowledge(agentId: string) {
  try {
    await classStore.acknowledgeAnomaly(agentId)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to acknowledge anomaly'
  }
}
</script>

<template>
  <div class="p-6 space-y-5">

    <!-- Header row -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <button
          v-for="type in (['', 'misclassified', 'ambiguous', 'unclassifiable'] as const)"
          :key="type"
          class="px-3 py-1.5 rounded-md text-[12px] font-medium transition-colors capitalize"
          :class="filterType === type
            ? 'bg-indigo-600 text-white'
            : ''"
          :style="filterType === type ? '' : `background: var(--surface); border: 1px solid var(--border); color: var(--text-2);`"
          :aria-label="`Filter by ${type || 'all'} classification`"
          :aria-pressed="filterType === type"
          role="button"
          @click="applyFilter(type as ClassificationVerdict | '')"
        >
          {{ type || 'All' }}
        </button>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="text-[13px] rounded-xl px-5 py-4" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
      {{ error }}
    </div>

    <!-- Loading -->
    <div v-if="classStore.isLoading" class="flex items-center justify-center py-20 text-[13px]" style="color: var(--text-3);" aria-live="polite" role="status">
      Loading…
    </div>

    <!-- Empty state -->
    <div
      v-else-if="classStore.results.length === 0"
      class="flex flex-col items-center justify-center py-20"
      style="color: var(--text-3);"
    >
      <svg class="w-10 h-10 mb-3 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <p class="text-[14px] font-medium" style="color: var(--text-3);">No anomalies found</p>
      <p class="text-[12px] mt-1">Run a sync and configure fingerprints to get started.</p>
    </div>

    <!-- Table -->
    <div v-else class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
      <table class="w-full border-collapse">
        <thead>
          <tr style="background: var(--surface-inset); border-bottom: 1px solid var(--border);">
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Hostname</th>
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Current Group</th>
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Suggested Group</th>
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Classification</th>
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Computed</th>
            <th scope="col" class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="result in classStore.results"
            :key="result.agent_id"
            class="last:border-0 transition-colors"
            style="border-bottom: 1px solid var(--border-light);"
            :class="{ 'opacity-40': result.acknowledged }"
          >
            <td class="px-4 py-3">
              <router-link
                :to="`/agents/${result.agent_id}`"
                class="text-[13px] font-medium text-indigo-600 hover:text-indigo-800 no-underline"
              >
                {{ result.hostname }}
              </router-link>
            </td>
            <td class="px-4 py-3 text-[13px]" style="color: var(--text-2);">{{ result.current_group_name }}</td>
            <td class="px-4 py-3 text-[13px]" style="color: var(--text-3);">{{ result.suggested_group_name ?? '—' }}</td>
            <td class="px-4 py-3">
              <span
                class="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold capitalize"
                :class="{
                  'bg-amber-100 text-amber-700': result.classification === 'misclassified',
                  'bg-orange-100 text-orange-700': result.classification === 'ambiguous',
                  ' text-muted': result.classification === 'unclassifiable',
                  'bg-emerald-100 text-emerald-700': result.classification === 'correct',
                }" style="background: var(--surface-hover);"
              >
                {{ result.classification }}
              </span>
            </td>
            <td class="px-4 py-3 text-[12px]" style="color: var(--text-3);">{{ formatRelativeTime(result.computed_at) }}</td>
            <td class="px-4 py-3">
              <button
                v-if="!result.acknowledged"
                class="px-3 py-1 rounded text-[12px] transition-colors"
                style="border: 1px solid var(--border); color: var(--text-2);"
                :aria-label="`Acknowledge anomaly for ${result.hostname}`"
                @click="acknowledge(result.agent_id)"
              >
                Acknowledge
              </button>
              <span v-else class="text-[12px] font-medium text-emerald-500">Reviewed</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
</template>
