<!--
  Compliance Control Detail — shows a single control's current status,
  violations, and historical trend.
-->
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useComplianceStore } from '@/stores/useComplianceStore'
import { useToast } from '@/composables/useToast'
import * as complianceApi from '@/api/compliance'

const route = useRoute()
const store = useComplianceStore()
const toast = useToast()

const controlId = computed(() => route.params.controlId as string)
const isRunning = ref(false)

const currentResult = computed(() => {
  if (!store.latestResults) return null
  return store.latestResults.results.find(r => r.control_id === controlId.value) ?? null
})

function statusBadgeStyle(status: string): { text: string; style: string } {
  switch (status) {
    case 'pass': return { text: 'Pass', style: 'background: var(--success-bg); color: var(--success-text);' }
    case 'warning': return { text: 'Warning', style: 'background: var(--warn-bg); color: var(--warn-text);' }
    case 'fail': return { text: 'Fail', style: 'background: var(--error-bg); color: var(--error-text);' }
    case 'error': return { text: 'Error', style: 'background: var(--error-bg); color: var(--error-text);' }
    default: return { text: 'N/A', style: 'background: var(--surface-inset); color: var(--text-3);' }
  }
}

function trendStatusStyle(status: string): string {
  switch (status) {
    case 'pass': return 'background: var(--status-ok);'
    case 'warning': return 'background: var(--status-warn);'
    case 'fail': return 'background: var(--status-error);'
    case 'error': return 'background: var(--status-error);'
    default: return 'background: var(--surface-inset);'
  }
}

async function handleRunCheck() {
  isRunning.value = true
  try {
    const result = await complianceApi.runCompliance()
    toast.show(`Check complete: ${result.passed} pass, ${result.failed} fail`)
    await loadData()
  } catch {
    toast.show('Check failed', 'error')
  } finally {
    isRunning.value = false
  }
}

async function loadData() {
  await Promise.all([
    store.fetchLatestResults(),
    store.fetchControlHistory(controlId.value),
  ])
}

onMounted(loadData)

watch(controlId, (newId, oldId) => {
  if (newId && newId !== oldId) loadData()
})
</script>

<template>
  <div class="max-w-5xl mx-auto px-4 py-6">
    <!-- Breadcrumb -->
    <div class="flex items-center gap-2 mb-4 text-sm" style="color: var(--text-3);">
      <router-link to="/compliance" class="hover:underline">Compliance</router-link>
      <span>/</span>
      <span style="color: var(--text-1);">{{ controlId }}</span>
    </div>

    <!-- Loading -->
    <div v-if="store.isLoading && !currentResult" class="text-center py-12" style="color: var(--text-3);">Loading control data...</div>

    <template v-else-if="currentResult">
      <!-- Header -->
      <div class="flex items-start justify-between mb-6">
        <div>
          <div class="flex items-center gap-3">
            <h1 class="text-2xl font-bold" style="color: var(--heading);">{{ currentResult.control_id }}</h1>
            <span
              :style="statusBadgeStyle(currentResult.status).style"
              class="px-3 py-1 rounded-full text-sm font-medium"
            >
              {{ statusBadgeStyle(currentResult.status).text }}
            </span>
          </div>
          <p class="text-sm mt-1" style="color: var(--text-2);">{{ currentResult.control_name }}</p>
          <p class="text-xs mt-1" style="color: var(--text-3);">
            {{ currentResult.framework_id }} / {{ currentResult.category }}
          </p>
        </div>
        <button
          :disabled="isRunning"
          class="px-4 py-2 bg-[var(--brand-primary)] text-white rounded-lg hover:opacity-90 disabled:opacity-50 text-sm font-medium"
          @click="handleRunCheck"
        >
          {{ isRunning ? 'Running...' : 'Run Check Now' }}
        </button>
      </div>

      <!-- Stats -->
      <div class="grid grid-cols-3 gap-4 mb-6">
        <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="text-xs" style="color: var(--text-3);">Total Endpoints</div>
          <div class="text-2xl font-bold mt-1" style="color: var(--text-1);">{{ currentResult.total_endpoints }}</div>
        </div>
        <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="text-xs" style="color: var(--text-3);">Compliant</div>
          <div class="text-2xl font-bold mt-1 text-[var(--success-text)]">{{ currentResult.compliant_endpoints }}</div>
        </div>
        <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="text-xs" style="color: var(--text-3);">Non-Compliant</div>
          <div class="text-2xl font-bold mt-1" :class="currentResult.non_compliant_endpoints > 0 ? 'text-[var(--error-text)]' : 'text-[var(--success-text)]'">
            {{ currentResult.non_compliant_endpoints }}
          </div>
        </div>
      </div>

      <!-- Evidence -->
      <div class="rounded-xl p-4 mb-6" style="background: var(--surface); border: 1px solid var(--border);">
        <div class="text-xs font-medium mb-1" style="color: var(--text-3);">Evidence Summary</div>
        <p class="text-sm" style="color: var(--text-1);">{{ currentResult.evidence_summary }}</p>
        <div class="text-xs mt-2" style="color: var(--text-3);">Last checked: {{ new Date(currentResult.checked_at).toLocaleString() }}</div>
      </div>

      <!-- Violations -->
      <div v-if="currentResult.violations.length > 0" class="mb-6">
        <h2 class="text-lg font-semibold mb-3" style="color: var(--heading);">
          Violations ({{ currentResult.violations.length }})
        </h2>
        <div class="overflow-x-auto rounded-lg" style="border: 1px solid var(--border);">
          <table class="min-w-full divide-y" style="border-color: var(--border);">
            <thead style="background: var(--surface-inset);">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Hostname</th>
                <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Detail</th>
                <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Application</th>
                <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Remediation</th>
              </tr>
            </thead>
            <tbody class="divide-y" style="background: var(--surface); border-color: var(--border);">
              <tr v-for="(v, i) in currentResult.violations" :key="i">
                <td class="px-4 py-3 text-sm font-medium" style="color: var(--text-1);">{{ v.agent_hostname }}</td>
                <td class="px-4 py-3 text-sm" style="color: var(--text-2);">{{ v.violation_detail }}</td>
                <td class="px-4 py-3 text-sm" style="color: var(--text-3);">
                  {{ v.app_name || '-' }}
                  <span v-if="v.app_version" class="text-xs"> v{{ v.app_version }}</span>
                </td>
                <td class="px-4 py-3 text-xs" style="color: var(--text-3);">{{ v.remediation }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Trend -->
      <div v-if="store.controlHistory && store.controlHistory.entries.length > 0">
        <h2 class="text-lg font-semibold mb-3" style="color: var(--heading);">
          Historical Trend ({{ store.controlHistory.total }} checks)
        </h2>
        <div class="flex gap-0.5 items-end h-8">
          <div
            v-for="(entry, i) in store.controlHistory.entries.slice().reverse().slice(-60)"
            :key="i"
            :style="trendStatusStyle(entry.status)"
            class="flex-1 rounded-sm min-w-[3px]"
            style="height: 100%;"
            :title="`${entry.status} — ${new Date(entry.checked_at).toLocaleDateString()}`"
          ></div>
        </div>
        <div class="flex justify-between text-xs mt-1" style="color: var(--text-3);">
          <span>Oldest</span>
          <span>Most Recent</span>
        </div>
      </div>
    </template>

    <!-- No data -->
    <div v-else class="text-center py-12" style="color: var(--text-3);">
      <p>No results found for control <strong>{{ controlId }}</strong>.</p>
      <p class="mt-2">Run a compliance check to generate results.</p>
    </div>
  </div>
</template>
