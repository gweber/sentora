<!--
  Enforcement Rules — taxonomy-based software policy enforcement.
  Shows summary, rules table with inline toggle, violations feed,
  and a create-rule dialog.
-->
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useEnforcementStore } from '@/stores/useEnforcementStore'
import { useToast } from '@/composables/useToast'
import type { CreateRuleRequest } from '@/api/enforcement'
import GroupPicker from '@/components/common/GroupPicker.vue'
import TagPicker from '@/components/common/TagPicker.vue'
import TaxonomyCategoryPicker from '@/components/common/TaxonomyCategoryPicker.vue'

const store = useEnforcementStore()
const toast = useToast()
const showCreateModal = ref(false)
const pendingDeleteId = ref<string | null>(null)

const newRule = ref<CreateRuleRequest>({
  name: '',
  taxonomy_category_id: '',
  type: 'required',
  severity: 'high',
  scope_groups: [],
  scope_tags: [],
  labels: [],
})

const labelsInput = ref('')

function statusBadgeStyle(status: string): { text: string; style: string } {
  return status === 'pass'
    ? { text: 'Pass', style: 'background: var(--success-bg); color: var(--success-text);' }
    : { text: 'Fail', style: 'background: var(--error-bg); color: var(--error-text);' }
}

function severityBadgeStyle(severity: string): string {
  switch (severity) {
    case 'critical': return 'background: var(--error-bg); color: var(--error-text);'
    case 'high': return 'background: var(--warning-bg); color: var(--warning-text);'
    case 'medium': return 'background: rgba(234, 179, 8, 0.15); color: var(--warning-text);'
    default: return 'background: var(--surface-inset); color: var(--text-3);'
  }
}

function typeBadgeStyle(type: string): string {
  switch (type) {
    case 'required': return 'background: var(--accent-bg); color: var(--accent-text);'
    case 'forbidden': return 'background: var(--error-bg); color: var(--error-text);'
    case 'allowlist': return 'background: rgba(168, 85, 247, 0.15); color: var(--text-2);'
    default: return 'background: var(--surface-inset); color: var(--text-3);'
  }
}

function ruleStatus(ruleId: string): string {
  const result = store.latestResults.find(r => r.rule_id === ruleId)
  return result?.status ?? 'N/A'
}

function ruleViolationCount(ruleId: string): number {
  const result = store.latestResults.find(r => r.rule_id === ruleId)
  return result?.violations?.length ?? 0
}

function ruleCheckedAt(ruleId: string): string {
  const result = store.latestResults.find(r => r.rule_id === ruleId)
  return result?.checked_at ? new Date(result.checked_at).toLocaleString() : 'Never'
}

async function handleCreate() {
  newRule.value.labels = labelsInput.value.split(',').map(s => s.trim()).filter(Boolean)
  await store.createRule(newRule.value)
  if (!store.error) {
    toast.show(`Rule "${newRule.value.name}" created`)
    showCreateModal.value = false
    newRule.value = { name: '', taxonomy_category_id: '', type: 'required', severity: 'high', scope_groups: [], scope_tags: [], labels: [] }
    labelsInput.value = ''
  }
}

async function handleRunAll() {
  await store.triggerRun()
  if (store.lastRunResult && !store.error) {
    const r = store.lastRunResult
    toast.show(`Check complete: ${r.passed} pass, ${r.failed} fail, ${r.total_violations} violations`)
  }
  await loadAll()
}

function confirmDelete(ruleId: string) {
  pendingDeleteId.value = ruleId
}

async function handleDelete() {
  if (!pendingDeleteId.value) return
  const id = pendingDeleteId.value
  const rule = store.rules.find(r => r.id === id)
  pendingDeleteId.value = null
  await store.deleteRule(id)
  if (!store.error) {
    toast.show(`Rule "${rule?.name ?? id}" deleted`)
  }
}

async function loadAll() {
  await Promise.all([
    store.fetchRules(),
    store.fetchSummary(),
    store.fetchLatestResults(),
  ])
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    if (pendingDeleteId.value) { pendingDeleteId.value = null; return }
    if (showCreateModal.value) { showCreateModal.value = false; return }
  }
}

onMounted(() => {
  loadAll()
  document.addEventListener('keydown', onKeydown)
})
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Breadcrumb -->
    <div class="flex items-center gap-2 mb-4 text-sm" style="color: var(--text-3);">
      <router-link to="/compliance" class="hover:underline">Compliance</router-link>
      <span>/</span>
      <span style="color: var(--text-1);">Enforcement Rules</span>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold" style="color: var(--heading);">Enforcement Rules</h1>
        <p class="text-sm mt-1" style="color: var(--text-3);">Taxonomy-based software policy enforcement</p>
      </div>
      <div class="flex gap-2">
        <button
          class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          style="background: var(--surface-hover); color: var(--text-2);"
          @click="showCreateModal = true"
        >
          Create Rule
        </button>
        <button
          :disabled="store.isRunning"
          class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors text-sm font-medium"
          @click="handleRunAll"
        >
          {{ store.isRunning ? 'Running...' : 'Run All Checks' }}
        </button>
      </div>
    </div>

    <!-- Error -->
    <div v-if="store.error" class="mb-4 p-3 rounded-lg text-sm" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
      {{ store.error }}
      <button class="ml-2 underline" @click="store.error = null">dismiss</button>
    </div>

    <!-- Summary cards -->
    <div v-if="store.summary" class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
      <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);">
        <div class="text-xs" style="color: var(--text-3);">Total Rules</div>
        <div class="text-2xl font-bold mt-1" style="color: var(--text-1);">{{ store.summary.total_rules }}</div>
      </div>
      <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);">
        <div class="text-xs" style="color: var(--text-3);">Enabled</div>
        <div class="text-2xl font-bold mt-1" style="color: var(--text-1);">{{ store.summary.enabled_rules }}</div>
      </div>
      <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);">
        <div class="text-xs" style="color: var(--text-3);">Passing</div>
        <div class="text-2xl font-bold mt-1 text-green-600">{{ store.summary.passing }}</div>
      </div>
      <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);">
        <div class="text-xs" style="color: var(--text-3);">Failing</div>
        <div class="text-2xl font-bold mt-1 text-red-600">{{ store.summary.failing }}</div>
      </div>
      <div class="rounded-xl p-4" style="background: var(--surface); border: 1px solid var(--border);">
        <div class="text-xs" style="color: var(--text-3);">Violations</div>
        <div class="text-2xl font-bold mt-1" :class="store.totalViolations > 0 ? 'text-red-600' : 'text-green-600'">
          {{ store.totalViolations }}
        </div>
      </div>
    </div>

    <!-- Rules table -->
    <div class="mb-8">
      <h2 class="text-lg font-semibold mb-3" style="color: var(--heading);">Rules</h2>
      <div class="overflow-x-auto rounded-lg" style="border: 1px solid var(--border);">
        <table class="min-w-full divide-y" style="border-color: var(--border);">
          <thead style="background: var(--surface-inset);">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Rule</th>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Type</th>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Severity</th>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Status</th>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Violations</th>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Last Checked</th>
              <th class="px-4 py-3 text-right text-xs font-medium uppercase" style="color: var(--text-3);">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y" style="background: var(--surface); border-color: var(--border);">
            <tr v-for="rule in store.rules" :key="rule.id">
              <td class="px-4 py-3">
                <div class="text-sm font-medium" style="color: var(--text-1);">{{ rule.name }}</div>
                <div class="text-xs" style="color: var(--text-3);">{{ rule.taxonomy_category_id }}</div>
                <div v-if="rule.labels.length" class="flex gap-1 mt-1">
                  <span v-for="label in rule.labels" :key="label" class="text-xs px-1.5 py-0.5 rounded" style="background: var(--surface-inset); color: var(--text-3);">{{ label }}</span>
                </div>
              </td>
              <td class="px-4 py-3">
                <span :style="typeBadgeStyle(rule.type)" class="px-2 py-0.5 rounded text-xs font-medium">{{ rule.type }}</span>
              </td>
              <td class="px-4 py-3">
                <span :style="severityBadgeStyle(rule.severity)" class="px-2 py-0.5 rounded text-xs font-medium">{{ rule.severity }}</span>
              </td>
              <td class="px-4 py-3">
                <span :style="statusBadgeStyle(ruleStatus(rule.id)).style" class="px-2 py-0.5 rounded text-xs font-medium">{{ statusBadgeStyle(ruleStatus(rule.id)).text }}</span>
              </td>
              <td class="px-4 py-3 text-sm" style="color: var(--text-2);">{{ ruleViolationCount(rule.id) }}</td>
              <td class="px-4 py-3 text-xs" style="color: var(--text-3);">{{ ruleCheckedAt(rule.id) }}</td>
              <td class="px-4 py-3 text-right space-x-2">
                <label class="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" :checked="rule.enabled" class="sr-only peer" @change="store.toggleRule(rule.id)">
                  <div class="w-8 h-4 bg-gray-300 peer-checked:bg-indigo-600 rounded-full transition-colors after:content-[''] after:absolute after:top-[1px] after:left-[1px] after:bg-white after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:after:translate-x-3.5"></div>
                </label>
                <button class="text-red-500 hover:text-red-700 text-xs" @click="confirmDelete(rule.id)">Delete</button>
              </td>
            </tr>
            <tr v-if="store.rules.length === 0">
              <td colspan="7" class="px-4 py-8 text-center text-sm" style="color: var(--text-3);">
                No enforcement rules configured. Create your first rule to start monitoring.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Link to unified violations view -->
    <div class="mt-4">
      <router-link
        to="/compliance"
        class="text-sm text-indigo-600 hover:underline"
      >
        View all violations (Enforcement + Compliance) →
      </router-link>
    </div>

    <!-- Delete confirmation dialog -->
    <Teleport to="body">
      <div
        v-if="pendingDeleteId"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        style="background: rgba(0,0,0,0.5);"
        @mousedown.self="pendingDeleteId = null"
      >
        <div class="rounded-xl p-6 w-full max-w-sm" style="background: var(--surface); border: 1px solid var(--border);">
          <h3 class="text-lg font-semibold mb-2" style="color: var(--heading);">Delete Rule?</h3>
          <p class="text-sm mb-4" style="color: var(--text-2);">
            This will permanently remove the rule and all its historical results. This action cannot be undone.
          </p>
          <div class="flex justify-end gap-2">
            <button
              class="px-4 py-2 rounded-lg text-sm"
              style="background: var(--surface-hover); color: var(--text-2);"
              @click="pendingDeleteId = null"
            >
              Cancel
            </button>
            <button
              class="px-4 py-2 rounded-lg text-sm font-medium"
              style="background: var(--error-bg); color: var(--error-text); border: 1px solid var(--error-border);"
              @click="handleDelete"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Create rule modal -->
    <Teleport to="body">
      <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center p-4" style="background: rgba(0,0,0,0.5);" @mousedown.self="showCreateModal = false">
        <div class="rounded-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto" style="background: var(--surface);">
          <h3 class="text-lg font-semibold mb-4" style="color: var(--heading);">Create Enforcement Rule</h3>
          <form class="space-y-3" @submit.prevent="handleCreate">
            <div>
              <label class="text-xs font-medium" style="color: var(--text-3);">Name</label>
              <input v-model="newRule.name" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-inset); border: 1px solid var(--border); color: var(--text-1);" required>
            </div>
            <div>
              <label class="text-xs font-medium" style="color: var(--text-3);">Description</label>
              <textarea v-model="newRule.description" rows="2" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-inset); border: 1px solid var(--border); color: var(--text-1);"></textarea>
            </div>
            <div>
              <label class="text-xs font-medium" style="color: var(--text-3);">Taxonomy Category</label>
              <TaxonomyCategoryPicker v-model="newRule.taxonomy_category_id" />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="text-xs font-medium" style="color: var(--text-3);">Type</label>
                <select v-model="newRule.type" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-inset); border: 1px solid var(--border); color: var(--text-1);">
                  <option value="required">Required</option>
                  <option value="forbidden">Forbidden</option>
                  <option value="allowlist">Allowlist</option>
                </select>
              </div>
              <div>
                <label class="text-xs font-medium" style="color: var(--text-3);">Severity</label>
                <select v-model="newRule.severity" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-inset); border: 1px solid var(--border); color: var(--text-1);">
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
            </div>
            <div>
              <label class="text-xs font-medium" style="color: var(--text-3);">Scope Groups (empty = all agents)</label>
              <GroupPicker v-model="newRule.scope_groups!" />
            </div>
            <div>
              <label class="text-xs font-medium" style="color: var(--text-3);">Scope Tags (empty = all agents)</label>
              <TagPicker v-model="newRule.scope_tags!" />
            </div>
            <div>
              <label class="text-xs font-medium" style="color: var(--text-3);">Labels (comma-separated, optional)</label>
              <input v-model="labelsInput" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-inset); border: 1px solid var(--border); color: var(--text-1);" placeholder="e.g. PCI-DSS 5.2.1, BSI SYS.2.1.A6">
            </div>
            <div class="flex justify-end gap-2 pt-2">
              <button type="button" class="px-4 py-2 rounded-lg text-sm" style="background: var(--surface-hover); color: var(--text-2);" @click="showCreateModal = false">Cancel</button>
              <button type="submit" class="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700">Create Rule</button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>
  </div>
</template>
