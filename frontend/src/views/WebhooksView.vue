<!--
  Webhooks management view — CRUD table for webhook endpoints.
  Admin-only. Allows creating, editing, testing, and deleting webhooks.
-->
<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import * as webhookApi from '@/api/webhooks'
import { useAsyncAction } from '@/composables/useAsyncAction'
import type { Webhook, WebhookCreateRequest, WebhookTestResponse } from '@/types/webhooks'
import { WEBHOOK_EVENTS } from '@/types/webhooks'

const { execute: guardedExecute } = useAsyncAction()
const webhooks = ref<Webhook[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)

// Create/Edit modal
const showModal = ref(false)
const editingId = ref<string | null>(null)
const formName = ref('')
const formUrl = ref('')
const formEvents = ref<string[]>([])
const formSecret = ref('')
const isSaving = ref(false)
const formError = ref<string | null>(null)

// Test result
const testingId = ref<string | null>(null)
const testResult = ref<WebhookTestResponse | null>(null)

// Delete confirmation
const deletingId = ref<string | null>(null)

const isEditing = computed(() => editingId.value !== null)

async function loadWebhooks() {
  isLoading.value = true
  error.value = null
  try {
    webhooks.value = await webhookApi.listWebhooks()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load webhooks'
  } finally {
    isLoading.value = false
  }
}

function openCreateModal() {
  editingId.value = null
  formName.value = ''
  formUrl.value = ''
  formEvents.value = []
  formSecret.value = ''
  formError.value = null
  showModal.value = true
}

function openEditModal(wh: Webhook) {
  editingId.value = wh.id
  formName.value = wh.name
  formUrl.value = wh.url
  formEvents.value = [...wh.events]
  formSecret.value = ''
  formError.value = null
  showModal.value = true
}

function toggleEvent(event: string) {
  const idx = formEvents.value.indexOf(event)
  if (idx >= 0) {
    formEvents.value.splice(idx, 1)
  } else {
    formEvents.value.push(event)
  }
}

async function handleSave() {
  formError.value = null
  if (!formName.value.trim()) { formError.value = 'Name is required'; return }
  if (!formUrl.value.trim()) { formError.value = 'URL is required'; return }
  if (formEvents.value.length === 0) { formError.value = 'Select at least one event'; return }

  isSaving.value = true
  try {
    if (isEditing.value) {
      await webhookApi.updateWebhook(editingId.value!, {
        name: formName.value.trim(),
        url: formUrl.value.trim(),
        events: formEvents.value,
      })
    } else {
      const payload: WebhookCreateRequest = {
        name: formName.value.trim(),
        url: formUrl.value.trim(),
        events: formEvents.value,
      }
      if (formSecret.value.trim()) payload.secret = formSecret.value.trim()
      await webhookApi.createWebhook(payload)
    }
    showModal.value = false
    await loadWebhooks()
  } catch (err) {
    formError.value = err instanceof Error ? err.message : 'Save failed'
  } finally {
    isSaving.value = false
  }
}

let _testClearTimer: ReturnType<typeof setTimeout> | null = null

async function handleTest(id: string) {
  await guardedExecute(async () => {
    testingId.value = id
    testResult.value = null
    try {
      testResult.value = await webhookApi.testWebhook(id)
    } catch {
      testResult.value = { success: false, status_code: null, response_time_ms: 0 }
    }
    if (_testClearTimer) clearTimeout(_testClearTimer)
    _testClearTimer = setTimeout(() => {
      if (testingId.value === id) {
        testingId.value = null
        testResult.value = null
      }
      _testClearTimer = null
    }, 5000)
  })
}

async function handleToggleEnabled(wh: Webhook) {
  try {
    await webhookApi.updateWebhook(wh.id, { enabled: !wh.enabled })
    await loadWebhooks()
  } catch (err) {
    error.value = err instanceof Error ? err.message : `Failed to ${wh.enabled ? 'disable' : 'enable'} webhook`
  }
}

async function handleDelete() {
  if (!deletingId.value) return
  try {
    await webhookApi.deleteWebhook(deletingId.value)
    deletingId.value = null
    await loadWebhooks()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Delete failed'
    deletingId.value = null
  }
}

function eventLabel(event: string): string {
  return event.replace('.', ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function eventColor(event: string): string {
  if (event.includes('completed')) return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  if (event.includes('failed')) return 'bg-red-50 text-red-600 border-red-200'
  if (event.includes('updated')) return 'bg-blue-50 text-blue-700 border-blue-200'
  return 'badge-neutral border'
}

function timeAgo(iso: string | null): string {
  if (!iso) return 'Never'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

onMounted(loadWebhooks)
onUnmounted(() => {
  if (_testClearTimer) clearTimeout(_testClearTimer)
})
</script>

<template>
  <div class="p-6 max-w-[960px]">

    <!-- Header -->
    <div class="flex items-center justify-between mb-5">
      <div>
        <h2 class="text-[15px] font-semibold" style="color: var(--heading);">Webhooks</h2>
        <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Receive HTTP notifications when events occur in Sentora</p>
      </div>
      <button
        class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-indigo-600 text-white text-[13px] font-medium hover:bg-indigo-700 transition-colors"
        @click="openCreateModal"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        Add Webhook
      </button>
    </div>

    <!-- Error -->
    <div v-if="error" class="mb-4 px-3 py-2 text-sm rounded-lg" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
      {{ error }}
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="text-center py-12 text-[13px]" style="color: var(--text-3);">Loading webhooks…</div>

    <!-- Empty state -->
    <div v-else-if="webhooks.length === 0" class="text-center py-16">
      <div class="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4" style="background: var(--surface-inset);">
        <svg class="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" style="color: var(--text-3);">
          <path stroke-linecap="round" stroke-linejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
        </svg>
      </div>
      <p class="text-[14px] font-medium mb-1" style="color: var(--text-2);">No webhooks configured</p>
      <p class="text-[12px]" style="color: var(--text-3);">Add a webhook to receive notifications for sync, classification, and fingerprint events.</p>
    </div>

    <!-- Webhook list -->
    <div v-else class="space-y-3">
      <div
        v-for="wh in webhooks"
        :key="wh.id"
        class="rounded-xl overflow-hidden transition-shadow hover:shadow-sm"
        style="background: var(--surface); border: 1px solid var(--border);"
      >
        <div class="px-5 py-4">
          <!-- Top row: name + status + actions -->
          <div class="flex items-center gap-3 mb-2.5">
            <div class="flex items-center gap-2 min-w-0 flex-1">
              <div
                class="w-2 h-2 rounded-full shrink-0"
                :class="wh.enabled ? 'bg-emerald-400' : 'bg-slate-300'"
                :title="wh.enabled ? 'Enabled' : 'Disabled'"
              />
              <h3 class="text-[14px] font-semibold truncate" style="color: var(--text-1);">{{ wh.name }}</h3>
              <span v-if="wh.failure_count > 0" class="shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-red-50 text-red-600 border border-red-200">
                {{ wh.failure_count }} failures
              </span>
            </div>

            <div class="flex items-center gap-1.5 shrink-0">
              <!-- Test -->
              <button
                class="px-2.5 py-1 rounded-md text-[11px] font-medium border transition-colors"
                :class="testingId === wh.id
                  ? (testResult?.success ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : testResult ? 'bg-red-50 text-red-600 border-red-200' : '')
                  : ''"
                :style="testingId !== wh.id ? 'background: var(--surface); color: var(--text-2); border-color: var(--border);' : testResult?.success ? '' : testResult ? '' : 'background: var(--surface-inset); color: var(--text-3); border-color: var(--border);'"
                :disabled="testingId === wh.id && !testResult"
                :aria-label="`Test webhook ${wh.name}`"
                @click="handleTest(wh.id)"
              >
                <template v-if="testingId === wh.id && !testResult">Testing…</template>
                <template v-else-if="testingId === wh.id && testResult?.success">OK {{ testResult.status_code }} ({{ Math.round(testResult.response_time_ms) }}ms)</template>
                <template v-else-if="testingId === wh.id && testResult">Failed</template>
                <template v-else>Test</template>
              </button>

              <!-- Toggle enabled -->
              <button
                class="px-2.5 py-1 rounded-md text-[11px] font-medium border transition-colors"
                :class="wh.enabled
                  ? 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100'
                  : 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'"
                :aria-label="wh.enabled ? `Disable webhook ${wh.name}` : `Enable webhook ${wh.name}`"
                @click="handleToggleEnabled(wh)"
              >
                {{ wh.enabled ? 'Disable' : 'Enable' }}
              </button>

              <!-- Edit -->
              <button
                class="px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors"
                style="background: var(--surface); color: var(--text-2); border: 1px solid var(--border);"
                :aria-label="`Edit webhook ${wh.name}`"
                @click="openEditModal(wh)"
              >Edit</button>

              <!-- Delete -->
              <button
                class="px-2.5 py-1 rounded-md text-[11px] font-medium text-red-500 hover:bg-red-50 hover:border-red-200 transition-colors"
                style="background: var(--surface); border: 1px solid var(--border);"
                :aria-label="`Delete webhook ${wh.name}`"
                @click="deletingId = wh.id"
              >Delete</button>
            </div>
          </div>

          <!-- URL -->
          <code class="text-[11px] font-mono block truncate mb-2" style="color: var(--text-3);">{{ wh.url }}</code>

          <!-- Events + last triggered -->
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-1.5 flex-wrap">
              <span
                v-for="event in wh.events"
                :key="event"
                class="text-[10px] font-medium px-1.5 py-0.5 rounded-full border"
                :class="eventColor(event)"
              >{{ eventLabel(event) }}</span>
            </div>
            <span class="text-[11px] shrink-0 ml-3" style="color: var(--text-3);">Last triggered: {{ timeAgo(wh.last_triggered_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Create/Edit modal ──────────────────────────────────────────────────── -->
    <Teleport to="body">
      <div
        v-if="showModal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        style="background: rgba(15,20,36,0.5)"
        @click.self="showModal = false"
      >
        <div
          class="rounded-2xl shadow-2xl w-full max-w-md overflow-hidden"
          style="background: var(--surface);"
          role="dialog"
          aria-modal="true"
          :aria-label="isEditing ? 'Edit webhook' : 'Create webhook'"
        >
          <!-- Modal header -->
          <div class="flex items-center justify-between px-5 py-4" style="border-bottom: 1px solid var(--border);">
            <h3 class="text-[15px] font-semibold" style="color: var(--text-1);">
              {{ isEditing ? 'Edit Webhook' : 'New Webhook' }}
            </h3>
            <button
              class="w-7 h-7 flex items-center justify-center rounded-lg transition-colors text-[18px] leading-none"
              style="color: var(--text-3);"
              aria-label="Close dialog"
              @click="showModal = false"
            >×</button>
          </div>

          <!-- Form -->
          <div class="px-5 py-4 space-y-4">
            <div v-if="formError" class="px-3 py-2 text-sm rounded-lg" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
              {{ formError }}
            </div>

            <!-- Name -->
            <div>
              <label for="wh-name" class="block text-xs font-medium mb-1" style="color: var(--text-2);">Name</label>
              <input
                id="wh-name"
                v-model="formName"
                type="text"
                placeholder="e.g. Slack notification"
                class="w-full px-3 py-2 text-sm rounded-lg outline-none transition" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              />
            </div>

            <!-- URL -->
            <div>
              <label for="wh-url" class="block text-xs font-medium mb-1" style="color: var(--text-2);">Endpoint URL</label>
              <input
                id="wh-url"
                v-model="formUrl"
                type="url"
                placeholder="https://example.com/webhook"
                class="w-full px-3 py-2 text-sm rounded-lg outline-none transition font-mono text-[12px]" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              />
            </div>

            <!-- Secret (create only) -->
            <div v-if="!isEditing">
              <label for="wh-secret" class="block text-xs font-medium mb-1" style="color: var(--text-2);">
                Secret <span class="font-normal" style="color: var(--text-3);">(optional — auto-generated if empty)</span>
              </label>
              <input
                id="wh-secret"
                v-model="formSecret"
                type="text"
                placeholder="HMAC signing secret"
                class="w-full px-3 py-2 text-sm rounded-lg outline-none transition font-mono text-[12px]" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              />
            </div>

            <!-- Events -->
            <div>
              <p class="text-xs font-medium mb-2" style="color: var(--text-2);">Events</p>
              <div class="grid grid-cols-2 gap-2">
                <button
                  v-for="event in WEBHOOK_EVENTS"
                  :key="event"
                  type="button"
                  class="flex items-center gap-2 px-3 py-2 rounded-lg border text-[12px] font-medium transition-colors text-left"
                  :class="formEvents.includes(event)
                    ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                    : 'hover:border-gray-300'"
                  :style="!formEvents.includes(event) ? 'background: var(--surface); border-color: var(--border); color: var(--text-2);' : ''"
                  :aria-pressed="formEvents.includes(event)"
                  @click="toggleEvent(event)"
                >
                  <svg
                    class="w-3.5 h-3.5 shrink-0"
                    :class="formEvents.includes(event) ? 'text-indigo-500' : 'text-gray-300'"
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"
                  >
                    <path v-if="formEvents.includes(event)" stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                    <path v-else stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  {{ eventLabel(event) }}
                </button>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="px-5 py-3 flex items-center justify-end gap-2" style="background: var(--surface-inset); border-top: 1px solid var(--border);">
            <button
              class="px-4 py-1.5 rounded-lg text-[13px] font-medium transition-colors"
              style="background: var(--surface-hover); color: var(--text-2);"
              @click="showModal = false"
            >Cancel</button>
            <button
              class="px-4 py-1.5 rounded-lg bg-indigo-600 text-white text-[13px] font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50"
              :disabled="isSaving"
              @click="handleSave"
            >
              {{ isSaving ? 'Saving…' : isEditing ? 'Update' : 'Create' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── Delete confirmation modal ──────────────────────────────────────────── -->
    <Teleport to="body">
      <div
        v-if="deletingId"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        style="background: rgba(15,20,36,0.5)"
        @click.self="deletingId = null"
      >
        <div class="rounded-xl shadow-2xl w-full max-w-sm p-6 text-center" style="background: var(--surface);" role="alertdialog" aria-modal="true" aria-label="Confirm webhook deletion">
          <div class="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-3">
            <svg class="w-6 h-6 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </div>
          <h3 class="text-[15px] font-semibold mb-1" style="color: var(--heading);">Delete webhook?</h3>
          <p class="text-[13px] mb-5" style="color: var(--text-3);">This action cannot be undone. The webhook will stop receiving events immediately.</p>
          <div class="flex items-center justify-center gap-2">
            <button
              class="px-4 py-2 rounded-lg text-[13px] font-medium transition-colors"
              style="background: var(--surface-hover); color: var(--text-2);"
              @click="deletingId = null"
            >Cancel</button>
            <button
              class="px-4 py-2 rounded-lg bg-red-600 text-white text-[13px] font-medium hover:bg-red-700 transition-colors"
              @click="handleDelete"
            >Delete</button>
          </div>
        </div>
      </div>
    </Teleport>

  </div>
</template>
