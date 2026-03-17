<!--
  Integrations view — tabbed UI for managing multiple data source integrations.

  Shows one tab per configured source (SentinelOne, CrowdStrike, etc.).
  Each tab contains the source-specific sync controls, progress, and history.
  When only one source is configured, the tab bar is hidden.
-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import SyncView from '@/views/SyncView.vue'

/** Available source integrations. Extend this array for future adapters. */
const SOURCES = [
  { key: 'sentinelone', label: 'SentinelOne', icon: 'S1' },
  { key: 'crowdstrike', label: 'CrowdStrike', icon: 'CS' },
] as const

type SourceKey = typeof SOURCES[number]['key']

const activeTab = ref<SourceKey>('sentinelone')
const showTabs = computed(() => SOURCES.length > 1)

/** Phase keys that belong to each source. */
const SOURCE_PHASES: Record<SourceKey, string[]> = {
  sentinelone: ['sites', 'groups', 'agents', 'apps', 'tags'],
  crowdstrike: ['cs_groups', 'cs_agents', 'cs_apps'],
}
</script>

<template>
  <div class="p-6 max-w-[860px]">
    <!-- Tab bar (hidden when only one source) -->
    <div
      v-if="showTabs"
      class="flex items-center gap-1 mb-5 rounded-lg p-1"
      style="background: var(--surface-inset); border: 1px solid var(--border);"
      role="tablist"
      aria-label="Integration source tabs"
    >
      <button
        v-for="src in SOURCES"
        :key="src.key"
        role="tab"
        :aria-selected="activeTab === src.key"
        :aria-controls="`panel-${src.key}`"
        class="flex items-center gap-2 px-4 py-2 rounded-md text-[13px] font-medium transition-all"
        :class="activeTab === src.key
          ? 'shadow-sm'
          : 'hover:opacity-80'"
        :style="activeTab === src.key
          ? 'background: var(--surface); color: var(--text-1); border: 1px solid var(--border);'
          : 'background: transparent; color: var(--text-3); border: 1px solid transparent;'"
        @click="activeTab = src.key"
      >
        <span
          class="w-5 h-5 flex items-center justify-center rounded text-[10px] font-bold shrink-0"
          :style="activeTab === src.key
            ? 'background: var(--brand-primary); color: white;'
            : 'background: var(--badge-bg); color: var(--text-3);'"
        >{{ src.icon }}</span>
        {{ src.label }}
      </button>
    </div>

    <!-- Tab panels -->
    <div
      v-for="src in SOURCES"
      :key="src.key"
      :id="`panel-${src.key}`"
      role="tabpanel"
      :aria-labelledby="`tab-${src.key}`"
      :hidden="activeTab !== src.key"
    >
      <SyncView
        v-if="activeTab === src.key"
        :source="src.key"
        :source-label="src.label"
        :phase-keys="SOURCE_PHASES[src.key]"
      />
    </div>
  </div>
</template>
