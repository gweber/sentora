<!--
  Compliance Settings — framework enable/disable, control configuration,
  custom control creation, and schedule management.
-->
<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useComplianceStore } from '@/stores/useComplianceStore'
import { useToast } from '@/composables/useToast'
import type { ControlResponse, CreateCustomControlRequest } from '@/api/compliance'

const store = useComplianceStore()
const toast = useToast()
const activeTab = ref<string>('')
const showCustomModal = ref(false)

const customForm = ref<CreateCustomControlRequest>({
  id: 'custom-',
  framework_id: '',
  name: '',
  description: '',
  category: '',
  severity: 'medium',
  check_type: 'custom_app_presence_check',
  parameters: {},
  scope_tags: [],
  scope_groups: [],
  remediation: '',
})

const frameworkControls = computed(() => {
  if (!store.activeFramework) return []
  return store.activeFramework.controls
})

const controlsByCategory = computed(() => {
  const groups: Record<string, ControlResponse[]> = {}
  for (const ctrl of frameworkControls.value) {
    if (!groups[ctrl.category]) groups[ctrl.category] = []
    groups[ctrl.category]!.push(ctrl)
  }
  return groups
})

async function handleToggleFramework(frameworkId: string, enabled: boolean) {
  await store.toggleFramework(frameworkId, enabled)
  if (!store.error) {
    toast.show(`Framework ${frameworkId} ${enabled ? 'enabled' : 'disabled'}`)
  }
  await store.fetchFrameworks()
}

async function handleToggleControl(controlId: string, enabled: boolean) {
  await store.configureControl(controlId, { enabled })
  if (!store.error) {
    toast.show(`Control ${controlId} ${enabled ? 'enabled' : 'disabled'}`)
  }
  if (activeTab.value) {
    await store.fetchFrameworkDetail(activeTab.value)
  }
}

async function selectFramework(frameworkId: string) {
  activeTab.value = frameworkId
  await store.fetchFrameworkDetail(frameworkId)
}

async function handleCreateCustom() {
  const name = customForm.value.name
  await store.createCustomControl(customForm.value)
  if (!store.error) {
    toast.show(`Custom control "${name}" created`)
  }
  showCustomModal.value = false
  customForm.value = {
    id: 'custom-',
    framework_id: activeTab.value,
    name: '',
    description: '',
    category: '',
    severity: 'medium',
    check_type: 'custom_app_presence_check',
    parameters: {},
    scope_tags: [],
    scope_groups: [],
    remediation: '',
  }
  if (activeTab.value) {
    await store.fetchFrameworkDetail(activeTab.value)
  }
}

async function handleUpdateSchedule(field: string, value: unknown) {
  await store.updateSchedule({ [field]: value })
  if (!store.error) {
    toast.show('Schedule updated')
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && showCustomModal.value) {
    showCustomModal.value = false
  }
}

onMounted(async () => {
  document.addEventListener('keydown', onKeydown)
  await Promise.all([store.fetchFrameworks(), store.fetchSchedule()])
})
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Breadcrumb -->
    <div class="flex items-center gap-2 mb-4 text-sm" style="color: var(--text-3);">
      <router-link to="/compliance" class="hover:underline">Compliance</router-link>
      <span>/</span>
      <span style="color: var(--text-1);">Settings</span>
    </div>

    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold" style="color: var(--heading);">Compliance Settings</h1>
        <p class="text-sm mt-1" style="color: var(--text-3);">Configure frameworks, controls, and check schedule</p>
      </div>
      <router-link
        to="/compliance"
        class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        style="background: var(--surface-hover); color: var(--text-2);"
      >
        Back to Dashboard
      </router-link>
    </div>

    <!-- Error -->
    <div v-if="store.error" class="mb-4 p-3 rounded-lg text-sm" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
      {{ store.error }}
      <button class="ml-2 underline" @click="store.error = null">dismiss</button>
    </div>

    <!-- Framework toggles -->
    <section class="mb-8">
      <h2 class="text-lg font-semibold mb-4" style="color: var(--heading);">Frameworks</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div
          v-for="fw in store.frameworks"
          :key="fw.id"
          class="rounded-xl p-4 cursor-pointer transition-all"
          :style="{
            background: 'var(--surface)',
            border: activeTab === fw.id ? '2px solid var(--brand-primary)' : '1px solid var(--border)',
          }"
          @click="selectFramework(fw.id)"
        >
          <div class="flex items-center justify-between mb-2">
            <div class="font-medium text-sm" style="color: var(--text-1);">{{ fw.name }}</div>
            <label class="relative inline-flex items-center cursor-pointer" @click.stop>
              <input
                type="checkbox"
                :checked="fw.enabled"
                class="sr-only peer"
                @change="handleToggleFramework(fw.id, !fw.enabled)"
              >
              <div class="w-9 h-5 bg-[var(--surface-hover)] peer-checked:bg-[var(--brand-primary)] rounded-full transition-colors after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4"></div>
            </label>
          </div>
          <p class="text-xs mb-2" style="color: var(--text-3);">{{ fw.description }}</p>
          <div class="text-xs" style="color: var(--text-3);">
            {{ fw.enabled_controls }}/{{ fw.total_controls }} controls enabled
          </div>
        </div>
      </div>
    </section>

    <!-- Controls for selected framework -->
    <section v-if="store.activeFramework" class="mb-8">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold" style="color: var(--heading);">
          Controls — {{ store.activeFramework.name }}
        </h2>
        <button
          class="px-3 py-1.5 bg-[var(--brand-primary)] text-white rounded-lg text-sm hover:bg-[var(--brand-primary-dark)] transition-colors"
          @click="showCustomModal = true; customForm.framework_id = activeTab"
        >
          Add Custom Control
        </button>
      </div>

      <!-- Disclaimer -->
      <div class="mb-4 p-3 rounded-lg text-xs" style="background: var(--surface-inset); color: var(--text-3); border: 1px solid var(--border);">
        {{ store.activeFramework.disclaimer }}
      </div>

      <!-- Controls grouped by category -->
      <div v-for="(controls, category) in controlsByCategory" :key="category" class="mb-6">
        <h3 class="text-sm font-semibold mb-2" style="color: var(--text-2);">{{ category }}</h3>
        <div class="space-y-2">
          <div
            v-for="ctrl in controls"
            :key="ctrl.id"
            class="rounded-lg p-3"
            style="background: var(--surface); border: 1px solid var(--border);"
          >
            <div class="flex items-start justify-between">
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <span class="text-xs font-mono px-1.5 py-0.5 rounded" style="background: var(--surface-inset); color: var(--text-3);">{{ ctrl.id }}</span>
                  <span class="text-sm font-medium" style="color: var(--text-1);">{{ ctrl.name }}</span>
                  <span v-if="ctrl.is_custom" class="text-xs px-1.5 py-0.5 rounded" style="background: rgba(168, 85, 247, 0.15); color: var(--text-2);">Custom</span>
                  <span v-if="ctrl.hipaa_type" class="text-xs px-1.5 py-0.5 rounded" style="background: var(--accent-bg); color: var(--accent-text);">{{ ctrl.hipaa_type }}</span>
                  <span v-if="ctrl.bsi_level" class="text-xs px-1.5 py-0.5 rounded" style="background: var(--surface-inset); color: var(--text-3);">{{ ctrl.bsi_level }}</span>
                </div>
                <p class="text-xs mt-1" style="color: var(--text-3);">{{ ctrl.description }}</p>
                <div v-if="ctrl.scope_tags.length || ctrl.scope_groups.length" class="flex gap-1 mt-1">
                  <span
                    v-for="tag in ctrl.scope_tags"
                    :key="tag"
                    class="text-xs px-1.5 py-0.5 rounded"
                    style="background: var(--accent-bg); color: var(--accent-text);"
                  >
                    {{ tag }}
                  </span>
                  <span
                    v-for="group in ctrl.scope_groups"
                    :key="group"
                    class="text-xs px-1.5 py-0.5 rounded"
                    style="background: var(--scope-group-bg); color: white;"
                  >
                    {{ group }}
                  </span>
                </div>
              </div>
              <label class="relative inline-flex items-center cursor-pointer ml-4">
                <input
                  type="checkbox"
                  :checked="ctrl.enabled"
                  class="sr-only peer"
                  @change="handleToggleControl(ctrl.id, !ctrl.enabled)"
                >
                <div class="w-9 h-5 bg-[var(--surface-hover)] peer-checked:bg-[var(--brand-primary)] rounded-full transition-colors after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4"></div>
              </label>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Schedule -->
    <section v-if="store.schedule" class="mb-8">
      <h2 class="text-lg font-semibold mb-4" style="color: var(--heading);">Check Schedule</h2>
      <div class="rounded-xl p-4 space-y-4" style="background: var(--surface); border: 1px solid var(--border);">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-sm font-medium" style="color: var(--text-1);">Run after sync</div>
            <div class="text-xs" style="color: var(--text-3);">Automatically run compliance checks after each successful data sync</div>
          </div>
          <label class="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              :checked="store.schedule.run_after_sync"
              class="sr-only peer"
              @change="handleUpdateSchedule('run_after_sync', !store.schedule?.run_after_sync)"
            >
            <div class="w-9 h-5 bg-[var(--surface-hover)] peer-checked:bg-[var(--brand-primary)] rounded-full transition-colors after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4"></div>
          </label>
        </div>
        <div class="flex items-center justify-between">
          <div>
            <div class="text-sm font-medium" style="color: var(--text-1);">Schedule enabled</div>
            <div class="text-xs" style="color: var(--text-3);">Enable or disable the compliance check schedule entirely</div>
          </div>
          <label class="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              :checked="store.schedule.enabled"
              class="sr-only peer"
              @change="handleUpdateSchedule('enabled', !store.schedule?.enabled)"
            >
            <div class="w-9 h-5 bg-[var(--surface-hover)] peer-checked:bg-[var(--brand-primary)] rounded-full transition-colors after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4"></div>
          </label>
        </div>
      </div>
    </section>

    <!-- Custom control modal -->
    <Teleport to="body">
      <div
        v-if="showCustomModal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        style="background: rgba(0,0,0,0.5);"
        @mousedown.self="showCustomModal = false"
      >
        <div class="rounded-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto" style="background: var(--surface);">
          <h3 class="text-lg font-semibold mb-4" style="color: var(--heading);">Create Custom Control</h3>
          <form class="space-y-3" @submit.prevent="handleCreateCustom">
            <div>
              <label class="text-xs font-medium" style="color: var(--text-3);">Control ID</label>
              <input v-model="customForm.id" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-inset); border: 1px solid var(--border); color: var(--text-1);" placeholder="custom-my-check" required>
            </div>
            <div>
              <label class="text-xs font-medium" style="color: var(--text-3);">Name</label>
              <input v-model="customForm.name" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-inset); border: 1px solid var(--border); color: var(--text-1);" required>
            </div>
            <div>
              <label class="text-xs font-medium" style="color: var(--text-3);">Description</label>
              <textarea v-model="customForm.description" rows="2" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-inset); border: 1px solid var(--border); color: var(--text-1);" required></textarea>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="text-xs font-medium" style="color: var(--text-3);">Category</label>
                <input v-model="customForm.category" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-inset); border: 1px solid var(--border); color: var(--text-1);" required>
              </div>
              <div>
                <label class="text-xs font-medium" style="color: var(--text-3);">Severity</label>
                <select v-model="customForm.severity" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-inset); border: 1px solid var(--border); color: var(--text-1);">
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
            </div>
            <div>
              <label class="text-xs font-medium" style="color: var(--text-3);">Check Type</label>
              <select v-model="customForm.check_type" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-inset); border: 1px solid var(--border); color: var(--text-1);">
                <option value="custom_app_presence_check">Custom App Presence</option>
                <option value="required_app_check">Required App</option>
                <option value="prohibited_app_check">Prohibited App</option>
                <option value="agent_version_check">Agent Version</option>
                <option value="agent_online_check">Agent Online</option>
                <option value="unclassified_threshold_check">Unclassified Threshold</option>
              </select>
            </div>
            <div>
              <label class="text-xs font-medium" style="color: var(--text-3);">Remediation</label>
              <input v-model="customForm.remediation" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-inset); border: 1px solid var(--border); color: var(--text-1);">
            </div>
            <div class="flex justify-end gap-2 pt-2">
              <button type="button" class="px-4 py-2 rounded-lg text-sm" style="background: var(--surface-hover); color: var(--text-2);" @click="showCustomModal = false">Cancel</button>
              <button type="submit" class="px-4 py-2 bg-[var(--brand-primary)] text-white rounded-lg text-sm hover:bg-[var(--brand-primary-dark)]">Create</button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>
  </div>
</template>
