<!--
  Compliance Dashboard — aggregated compliance scores, control status, and violations.
  Shows per-framework scores, filterable control results, and current violations.
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useComplianceStore } from '@/stores/useComplianceStore'
import { useToast } from '@/composables/useToast'
import * as complianceApi from '@/api/compliance'
import type { UnifiedViolationListResponse } from '@/api/compliance'

const toast = useToast()

const store = useComplianceStore()
const router = useRouter()
const filterFramework = ref<string>('')
const filterSeverity = ref<string>('')
const violationPage = ref(1)
const violationSource = ref<string>('')
const unifiedViolations = ref<UnifiedViolationListResponse | null>(null)

const scoreColorStyle = computed(() => {
  const s = store.overallScore
  if (s >= 90) return 'color: var(--status-ok);'
  if (s >= 70) return 'color: var(--status-warn);'
  return 'color: var(--status-error);'
})

const filteredResults = computed(() => {
  if (!store.latestResults) return []
  let results = store.latestResults.results
  if (filterFramework.value) {
    results = results.filter(r => r.framework_id === filterFramework.value)
  }
  if (filterSeverity.value) {
    results = results.filter(r => r.severity === filterSeverity.value)
  }
  return results
})

function statusBadgeStyle(status: string): { text: string; style: string } {
  switch (status) {
    case 'pass': return { text: 'Pass', style: 'background: var(--success-bg); color: var(--success-text);' }
    case 'warning': return { text: 'Warn', style: 'background: var(--warn-bg); color: var(--warn-text);' }
    case 'fail': return { text: 'Fail', style: 'background: var(--error-bg); color: var(--error-text);' }
    case 'error': return { text: 'Err', style: 'background: var(--error-bg); color: var(--error-text);' }
    default: return { text: 'N/A', style: 'background: var(--surface-inset); color: var(--text-3);' }
  }
}

function severityBadgeStyle(severity: string): string {
  switch (severity) {
    case 'critical': return 'background: var(--error-bg); color: var(--error-text);'
    case 'high': return 'background: var(--warn-bg); color: var(--warn-text);'
    case 'medium': return 'background: rgba(234, 179, 8, 0.15); color: var(--warn-text);'
    default: return 'background: var(--surface-inset); color: var(--text-3);'
  }
}

function fwScoreColorStyle(score: number): string {
  if (score >= 90) return 'color: var(--status-ok);'
  if (score >= 70) return 'color: var(--status-warn);'
  return 'color: var(--status-error);'
}

async function handleRunAll() {
  await store.triggerRun()
  if (store.lastRunResult && !store.error) {
    const r = store.lastRunResult
    toast.show(`Compliance check complete: ${r.passed} pass, ${r.failed} fail, ${r.warning} warn`)
  }
  await loadAll()
}

function navigateToControl(controlId: string) {
  router.push({ name: 'compliance-control', params: { controlId } })
}

async function downloadViolations() {
  try {
    const blob = await complianceApi.downloadViolationsExport(filterFramework.value || undefined)
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'compliance-violations.csv'
    a.click()
    URL.revokeObjectURL(a.href)
  } catch {
    // download failed — silently ignore
  }
}

async function loadUnifiedViolations(page: number = 1) {
  violationPage.value = page
  unifiedViolations.value = await complianceApi.listUnifiedViolations({
    source: violationSource.value || undefined,
    severity: filterSeverity.value || undefined,
    page,
    page_size: 20,
  })
}

async function loadAll() {
  await Promise.all([
    store.fetchDashboard(),
    store.fetchLatestResults(),
    loadUnifiedViolations(1),
  ])
}

onMounted(loadAll)
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold" style="color: var(--heading);">Compliance Dashboard</h1>
        <p class="text-sm mt-1" style="color: var(--text-3);">
          Endpoint software compliance monitoring across SOC 2, PCI DSS, HIPAA, and BSI IT-Grundschutz
        </p>
      </div>
      <div class="flex gap-2">
        <router-link
          to="/compliance/platform"
          class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          style="background: var(--surface-hover); color: var(--text-2);"
        >
          Platform Audit
        </router-link>
        <router-link
          to="/compliance/settings"
          class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          style="background: var(--surface-hover); color: var(--text-2);"
        >
          Settings
        </router-link>
        <button
          :disabled="store.isRunning"
          class="px-4 py-2 bg-[var(--brand-primary)] text-white rounded-lg hover:bg-[var(--brand-primary-dark)] disabled:opacity-50 transition-colors text-sm font-medium"
          @click="handleRunAll"
        >
          {{ store.isRunning ? 'Running...' : 'Run All Checks' }}
        </button>
      </div>
    </div>

    <!-- Disclaimer -->
    <div class="mb-6 p-3 rounded-lg text-xs" style="background: var(--surface-inset); color: var(--text-3); border: 1px solid var(--border);">
      Sentora monitors endpoint software compliance as part of your broader compliance program.
      It provides automated evidence collection and continuous monitoring — not certification.
    </div>

    <!-- Error -->
    <div v-if="store.error" class="mb-4 p-3 rounded-lg text-sm" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
      {{ store.error }}
      <button class="ml-2 underline" @click="store.error = null">dismiss</button>
    </div>

    <!-- Loading -->
    <div v-if="store.isLoading && !store.dashboard" class="text-center py-12" style="color: var(--text-3);">Loading compliance data...</div>

    <template v-else>
      <!-- Framework score cards -->
      <div v-if="store.dashboard" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <!-- Overall score -->
        <div class="rounded-xl p-4 col-span-1 md:col-span-2 lg:col-span-4" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="flex items-center justify-between">
            <div>
              <div class="text-sm" style="color: var(--text-3);">Overall Score</div>
              <div :style="scoreColorStyle" class="text-4xl font-bold mt-1">{{ store.overallScore }}%</div>
            </div>
            <div class="text-right">
              <div class="text-sm" style="color: var(--text-3);">Total Violations</div>
              <div class="text-2xl font-bold mt-1" :class="store.totalViolations > 0 ? 'text-[var(--error-text)]' : 'text-[var(--success-text)]'">
                {{ store.totalViolations }}
              </div>
            </div>
          </div>
        </div>

        <!-- Per-framework cards -->
        <div
          v-for="fw in store.dashboard.frameworks"
          :key="fw.framework_id"
          class="rounded-xl p-4"
          style="background: var(--surface); border: 1px solid var(--border);"
        >
          <div class="text-sm font-medium mb-2" style="color: var(--text-2);">{{ fw.framework_name }}</div>
          <div :style="fwScoreColorStyle(fw.score_percent)" class="text-3xl font-bold">{{ fw.score_percent }}%</div>
          <div class="flex gap-3 mt-2 text-xs" style="color: var(--text-3);">
            <span class="text-[var(--success-text)]">{{ fw.passed }} pass</span>
            <span class="text-[var(--error-text)]">{{ fw.failed }} fail</span>
            <span class="text-[var(--warn-text)]">{{ fw.warning }} warn</span>
          </div>
        </div>
      </div>

      <!-- Filters -->
      <div class="flex gap-3 mb-4">
        <select
          v-model="filterFramework"
          class="px-3 py-1.5 rounded-lg text-sm"
          style="background: var(--surface); border: 1px solid var(--border); color: var(--text-1);"
        >
          <option value="">All Frameworks</option>
          <option value="soc2">SOC 2</option>
          <option value="pci_dss_4">PCI DSS 4.0</option>
          <option value="hipaa">HIPAA</option>
          <option value="bsi_grundschutz">BSI IT-Grundschutz</option>
        </select>
        <select
          v-model="filterSeverity"
          class="px-3 py-1.5 rounded-lg text-sm"
          style="background: var(--surface); border: 1px solid var(--border); color: var(--text-1);"
        >
          <option value="">All Severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      <!-- Control status table -->
      <div v-if="store.latestResults" class="mb-8">
        <h2 class="text-lg font-semibold mb-3" style="color: var(--heading);">Control Status</h2>
        <div class="overflow-x-auto rounded-lg" style="border: 1px solid var(--border);">
          <table class="min-w-full divide-y" style="border-color: var(--border);">
            <thead style="background: var(--surface-inset);">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Control</th>
                <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Framework</th>
                <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Severity</th>
                <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Status</th>
                <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Endpoints</th>
                <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Evidence</th>
              </tr>
            </thead>
            <tbody class="divide-y" style="background: var(--surface); border-color: var(--border);">
              <tr
                v-for="r in filteredResults"
                :key="r.control_id"
                class="cursor-pointer hover:bg-opacity-50"
                style="transition: background 0.1s;"
                @click="navigateToControl(r.control_id)"
              >
                <td class="px-4 py-3">
                  <div class="text-sm font-medium" style="color: var(--text-1);">{{ r.control_id }}</div>
                  <div class="text-xs" style="color: var(--text-3);">{{ r.control_name }}</div>
                </td>
                <td class="px-4 py-3 text-sm uppercase" style="color: var(--text-3);">{{ r.framework_id }}</td>
                <td class="px-4 py-3">
                  <span :style="severityBadgeStyle(r.severity)" class="px-2 py-0.5 rounded text-xs font-medium">{{ r.severity }}</span>
                </td>
                <td class="px-4 py-3">
                  <span :style="statusBadgeStyle(r.status).style" class="px-2 py-0.5 rounded text-xs font-medium">{{ statusBadgeStyle(r.status).text }}</span>
                </td>
                <td class="px-4 py-3 text-sm" style="color: var(--text-2);">
                  {{ r.compliant_endpoints }}/{{ r.total_endpoints }}
                </td>
                <td class="px-4 py-3 text-xs max-w-xs truncate" style="color: var(--text-3);">{{ r.evidence_summary }}</td>
              </tr>
              <tr v-if="filteredResults.length === 0">
                <td colspan="6" class="px-4 py-8 text-center text-sm" style="color: var(--text-3);">
                  No results available. Enable frameworks and run a compliance check.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Unified Violations Feed -->
      <div v-if="unifiedViolations">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-lg font-semibold" style="color: var(--heading);">All Violations</h2>
          <div class="flex gap-2">
            <select
              v-model="violationSource"
              class="px-3 py-1.5 rounded-lg text-sm"
              style="background: var(--surface); border: 1px solid var(--border); color: var(--text-1);"
              @change="loadUnifiedViolations(1)"
            >
              <option value="">All Sources</option>
              <option value="compliance">Compliance</option>
              <option value="enforcement">Enforcement</option>
            </select>
            <button
              v-if="unifiedViolations.total > 0"
              class="text-sm text-[var(--brand-primary)] hover:underline"
              @click="downloadViolations"
            >
              Export CSV
            </button>
          </div>
        </div>
        <div v-if="unifiedViolations.total === 0" class="text-sm py-4" style="color: var(--text-3);">
          No violations found. All active checks are passing.
        </div>
        <div v-else class="space-y-2">
          <div
            v-for="(v, i) in unifiedViolations.violations"
            :key="i"
            class="rounded-lg p-3"
            style="background: var(--surface); border: 1px solid var(--border);"
          >
            <div class="flex items-start justify-between">
              <div>
                <div class="flex items-center gap-2">
                  <span :style="severityBadgeStyle(v.severity)" class="px-2 py-0.5 rounded text-xs font-medium">{{ v.severity }}</span>
                  <span
                    class="px-1.5 py-0.5 rounded text-xs font-medium"
                    :style="v.source === 'compliance' ? 'background: var(--accent-bg); color: var(--accent-text);' : 'background: rgba(168, 85, 247, 0.15); color: var(--text-2);'"
                  >
                    {{ v.source }}
                  </span>
                  <span class="text-sm font-medium" style="color: var(--text-1);">{{ v.agent_hostname }}</span>
                </div>
                <p class="text-sm mt-1" style="color: var(--text-2);">{{ v.violation_detail }}</p>
                <p class="text-xs mt-1" style="color: var(--text-3);">{{ v.control_name }} ({{ v.control_id }})</p>
              </div>
              <span v-if="v.remediation" class="text-xs ml-4 max-w-xs" style="color: var(--text-3);">{{ v.remediation }}</span>
            </div>
          </div>
          <!-- Pagination -->
          <div v-if="unifiedViolations.total > 20" class="flex justify-center gap-2 mt-4">
            <button
              :disabled="violationPage <= 1"
              class="px-3 py-1 rounded text-sm disabled:opacity-30"
              style="background: var(--surface-hover); color: var(--text-2);"
              @click="loadUnifiedViolations(violationPage - 1)"
            >
              Prev
            </button>
            <span class="px-3 py-1 text-sm" style="color: var(--text-3);">
              Page {{ violationPage }} of {{ Math.ceil(unifiedViolations.total / 20) }}
            </span>
            <button
              :disabled="violationPage >= Math.ceil(unifiedViolations.total / 20)"
              class="px-3 py-1 rounded text-sm disabled:opacity-30"
              style="background: var(--surface-hover); color: var(--text-2);"
              @click="loadUnifiedViolations(violationPage + 1)"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
