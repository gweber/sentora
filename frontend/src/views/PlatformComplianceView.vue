<!--
  Platform Compliance — Sentora's own security posture.
  Evaluates RBAC, audit logging, backups, MFA adoption against SOC 2 and ISO 27001.
  Separate from endpoint compliance which checks the managed fleet.
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useToast } from '@/composables/useToast'
import * as api from '@/api/platformCompliance'
import type { PlatformDashboard, PlatformReport } from '@/api/platformCompliance'

const toast = useToast()
const activeFramework = ref<'soc2' | 'iso27001'>('soc2')
const dashboard = ref<PlatformDashboard | null>(null)
const reports = ref<PlatformReport[]>([])
const loading = ref(true)
const generating = ref(false)
const error = ref<string | null>(null)

const scoreStyle = computed(() => {
  if (!dashboard.value) return 'color: var(--text-3);'
  const s = dashboard.value.score_percent
  if (s >= 90) return 'color: var(--status-ok);'
  if (s >= 70) return 'color: var(--status-warn);'
  return 'color: var(--status-error);'
})

const groupedControls = computed(() => {
  if (!dashboard.value) return {}
  const groups: Record<string, typeof dashboard.value.controls> = {}
  for (const ctrl of dashboard.value.controls) {
    if (!groups[ctrl.category]) groups[ctrl.category] = []
    groups[ctrl.category].push(ctrl)
  }
  return groups
})

function statusStyle(status: string): { icon: string; style: string } {
  switch (status) {
    case 'passing': return { icon: '\u2713', style: 'background: var(--success-bg); color: var(--success-text);' }
    case 'warning': return { icon: '!', style: 'background: var(--warning-bg); color: var(--warning-text);' }
    case 'failing': return { icon: '\u2717', style: 'background: var(--error-bg); color: var(--error-text);' }
    default: return { icon: '\u2014', style: 'background: var(--surface-inset); color: var(--text-3);' }
  }
}

async function loadDashboard() {
  loading.value = true
  error.value = null
  try {
    const [d, r] = await Promise.all([
      api.getDashboard(activeFramework.value),
      api.listReports(activeFramework.value),
    ])
    dashboard.value = d
    reports.value = r.reports
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load platform compliance data'
  } finally {
    loading.value = false
  }
}

async function switchFramework(fw: 'soc2' | 'iso27001') {
  activeFramework.value = fw
  await loadDashboard()
}

async function handleGenerate() {
  generating.value = true
  error.value = null
  try {
    const report = await api.generateReport(activeFramework.value)
    reports.value.unshift(report)
    toast.show('Platform compliance report generated')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to generate report'
  } finally {
    generating.value = false
  }
}

async function handleDelete(id: string) {
  try {
    await api.deleteReport(id)
    reports.value = reports.value.filter(r => r.id !== id)
    toast.show('Report deleted')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to delete report'
  }
}

function downloadCsv(id: string) {
  const url = api.getReportCsvUrl(id)
  const token = localStorage.getItem('sentora_token')
  fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    .then(r => r.blob())
    .then(blob => {
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `platform-compliance-${id.slice(0, 8)}.csv`
      a.click()
      URL.revokeObjectURL(a.href)
    })
    .catch(() => { error.value = 'Failed to download report' })
}

onMounted(loadDashboard)
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Breadcrumb -->
    <div class="flex items-center gap-2 mb-4 text-sm" style="color: var(--text-3);">
      <router-link to="/compliance" class="hover:underline">Compliance</router-link>
      <span>/</span>
      <span style="color: var(--text-1);">Platform Security</span>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold" style="color: var(--heading);">Platform Compliance</h1>
        <p class="text-sm mt-1" style="color: var(--text-3);">
          Sentora's own security posture — SOC 2 &amp; ISO 27001 self-assessment
        </p>
      </div>
      <button
        :disabled="generating"
        class="px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
        style="background: var(--brand-primary); color: white;"
        @click="handleGenerate"
      >
        {{ generating ? 'Generating...' : 'Generate Report' }}
      </button>
    </div>

    <!-- Framework tabs -->
    <div class="flex gap-2 mb-6">
      <button
        v-for="fw in [{ id: 'soc2' as const, label: 'SOC 2 Type II' }, { id: 'iso27001' as const, label: 'ISO 27001' }]"
        :key="fw.id"
        class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        :style="activeFramework === fw.id
          ? 'background: var(--brand-primary); color: white;'
          : 'background: var(--surface-hover); color: var(--text-2);'"
        @click="switchFramework(fw.id)"
      >
        {{ fw.label }}
      </button>
    </div>

    <!-- Error -->
    <div
      v-if="error"
      class="mb-4 p-3 rounded-lg text-sm"
      style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);"
      role="alert"
    >
      {{ error }}
      <button class="ml-2 underline" @click="error = null">dismiss</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-12" style="color: var(--text-3);">Evaluating platform controls...</div>

    <template v-else-if="dashboard">
      <!-- Score cards -->
      <div class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <div class="rounded-xl p-4 col-span-2 md:col-span-1" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="text-sm" style="color: var(--text-3);">Score</div>
          <div :style="scoreStyle" class="text-3xl font-bold mt-1">{{ dashboard.score_percent }}%</div>
        </div>
        <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="text-sm" style="color: var(--text-3);">Passing</div>
          <div class="text-2xl font-bold mt-1" style="color: var(--status-ok);">{{ dashboard.passing }}</div>
        </div>
        <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="text-sm" style="color: var(--text-3);">Warnings</div>
          <div class="text-2xl font-bold mt-1" style="color: var(--status-warn);">{{ dashboard.warning }}</div>
        </div>
        <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="text-sm" style="color: var(--text-3);">Failing</div>
          <div class="text-2xl font-bold mt-1" style="color: var(--status-error);">{{ dashboard.failing }}</div>
        </div>
        <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="text-sm" style="color: var(--text-3);">Total Controls</div>
          <div class="text-2xl font-bold mt-1" style="color: var(--text-1);">{{ dashboard.total_controls }}</div>
        </div>
      </div>

      <!-- Controls by category -->
      <div class="space-y-6 mb-10">
        <div v-for="(controls, category) in groupedControls" :key="category">
          <h2 class="text-lg font-semibold mb-3" style="color: var(--heading);">{{ category }}</h2>
          <div class="space-y-2">
            <div
              v-for="ctrl in controls"
              :key="ctrl.control_id"
              class="rounded-lg p-4"
              style="background: var(--surface); border: 1px solid var(--border);"
            >
              <div class="flex items-start justify-between">
                <div class="flex-1">
                  <div class="flex items-center gap-2">
                    <span
                      :style="statusStyle(ctrl.status).style"
                      class="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold"
                    >
                      {{ statusStyle(ctrl.status).icon }}
                    </span>
                    <span class="font-medium text-sm" style="color: var(--text-1);">{{ ctrl.reference }}</span>
                    <span class="text-sm" style="color: var(--text-2);">{{ ctrl.title }}</span>
                  </div>
                  <p class="text-sm mt-1 ml-8" style="color: var(--text-3);">{{ ctrl.evidence_summary }}</p>
                </div>
                <span class="text-xs whitespace-nowrap ml-4" style="color: var(--text-3);">
                  {{ ctrl.evidence_count }} evidence items
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Reports history -->
      <div v-if="reports.length">
        <h2 class="text-lg font-semibold mb-3" style="color: var(--heading);">Generated Reports</h2>
        <div class="overflow-x-auto rounded-lg" style="border: 1px solid var(--border);">
          <table class="min-w-full divide-y" style="border-color: var(--border);">
            <thead style="background: var(--surface-inset);">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Date</th>
                <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Framework</th>
                <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Period</th>
                <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Score</th>
                <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">By</th>
                <th class="px-4 py-3 text-right text-xs font-medium uppercase" style="color: var(--text-3);">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y" style="background: var(--surface); border-color: var(--border);">
              <tr v-for="report in reports" :key="report.id">
                <td class="px-4 py-3 text-sm" style="color: var(--text-1);">{{ new Date(report.generated_at).toLocaleString() }}</td>
                <td class="px-4 py-3 text-sm uppercase" style="color: var(--text-3);">{{ report.framework }}</td>
                <td class="px-4 py-3 text-sm" style="color: var(--text-3);">
                  {{ new Date(report.period_start).toLocaleDateString() }} — {{ new Date(report.period_end).toLocaleDateString() }}
                </td>
                <td class="px-4 py-3 text-sm">
                  <span
                    class="font-medium"
                    :style="report.passing_controls >= report.total_controls * 0.9 ? 'color: var(--status-ok);' : report.passing_controls >= report.total_controls * 0.7 ? 'color: var(--status-warn);' : 'color: var(--status-error);'"
                  >
                    {{ report.passing_controls }}/{{ report.total_controls }}
                  </span>
                </td>
                <td class="px-4 py-3 text-sm" style="color: var(--text-3);">{{ report.generated_by }}</td>
                <td class="px-4 py-3 text-sm text-right space-x-2">
                  <button
                    class="hover:underline text-sm"
                    style="color: var(--brand-primary);"
                    @click="downloadCsv(report.id)"
                  >
                    CSV
                  </button>
                  <button
                    class="hover:underline text-sm"
                    style="color: var(--error-text);"
                    @click="handleDelete(report.id)"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
