<!--
  API Keys management view.
  Lists all API keys with CRUD, rotation, and one-time key display.
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useApiKeysStore } from '@/stores/useApiKeysStore'
import type { APIKeyCreateRequest, APIKeyResponse } from '@/types/apiKeys'
import { AVAILABLE_SCOPES, READ_SCOPES } from '@/types/apiKeys'

const store = useApiKeysStore()

// ── Create dialog state ──────────────────────────────────────────────────────
const showCreate = ref(false)
const createForm = ref<APIKeyCreateRequest>({
  name: '',
  scopes: [],
  rate_limit_per_minute: 60,
  rate_limit_per_hour: 1000,
})
const createdFullKey = ref<string | null>(null)
const keyCopied = ref(false)

// ── Edit dialog state ────────────────────────────────────────────────────────
const showEdit = ref(false)
const editingKey = ref<APIKeyResponse | null>(null)
const editForm = ref({ name: '', description: '', scopes: [] as string[], rate_limit_per_minute: 60, rate_limit_per_hour: 1000 })

// ── Confirm dialog state ─────────────────────────────────────────────────────
const confirmAction = ref<'revoke' | 'rotate' | null>(null)
const confirmTarget = ref<APIKeyResponse | null>(null)
const rotatedFullKey = ref<string | null>(null)

// ── Key display tab ──────────────────────────────────────────────────────────
const showRevoked = ref(false)
const displayedKeys = computed(() => showRevoked.value ? store.revokedKeys : store.activeKeys)

onMounted(() => store.load())

// ── Scope helpers ────────────────────────────────────────────────────────────
function toggleScope(scopes: string[], scope: string): string[] {
  return scopes.includes(scope) ? scopes.filter(s => s !== scope) : [...scopes, scope]
}
function selectAllRead(scopes: string[]): string[] {
  const readScopes = READ_SCOPES.filter(s => !scopes.includes(s))
  return readScopes.length > 0 ? [...scopes, ...readScopes] : scopes.filter(s => !READ_SCOPES.includes(s))
}
const allReadSelected = (scopes: string[]) => READ_SCOPES.every(s => scopes.includes(s))

// ── Actions ──────────────────────────────────────────────────────────────────
async function handleCreate() {
  const fullKey = await store.create(createForm.value)
  if (fullKey) {
    createdFullKey.value = fullKey
    keyCopied.value = false
    showCreate.value = false
    createForm.value = { name: '', scopes: [], rate_limit_per_minute: 60, rate_limit_per_hour: 1000 }
  }
}

function openEdit(key: APIKeyResponse) {
  editingKey.value = key
  editForm.value = {
    name: key.name,
    description: key.description ?? '',
    scopes: [...key.scopes],
    rate_limit_per_minute: key.rate_limit_per_minute,
    rate_limit_per_hour: key.rate_limit_per_hour,
  }
  showEdit.value = true
}

async function handleEdit() {
  if (!editingKey.value) return
  const ok = await store.update(editingKey.value.id, editForm.value)
  if (ok) {
    showEdit.value = false
    editingKey.value = null
  }
}

async function handleConfirmAction() {
  if (!confirmTarget.value) return
  if (confirmAction.value === 'revoke') {
    await store.revoke(confirmTarget.value.id)
  } else if (confirmAction.value === 'rotate') {
    const fullKey = await store.rotate(confirmTarget.value.id)
    if (fullKey) {
      rotatedFullKey.value = fullKey
      keyCopied.value = false
    }
  }
  confirmAction.value = null
  confirmTarget.value = null
}

async function copyKey(key: string) {
  await navigator.clipboard.writeText(key)
  keyCopied.value = true
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

function timeAgo(iso: string | null): string {
  if (!iso) return 'Never'
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function scopeColor(scope: string): string {
  if (scope.endsWith(':read') || scope === 'read:all') return 'background: var(--info-bg); color: var(--info-text);'
  return 'background: var(--warn-bg); color: var(--warn-text);'
}
</script>

<template>
  <div class="p-6 max-w-6xl mx-auto space-y-6">

    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-semibold" style="color: var(--heading);">API Keys</h2>
        <p class="text-sm mt-0.5" style="color: var(--text-3);">
          Manage API keys for external integrations (SIEM, dashboards, automation).
        </p>
      </div>
      <button
        class="px-4 py-2 text-sm font-medium rounded-lg transition-colors"
        style="background: var(--brand-primary); color: white;"
        @click="showCreate = true"
      >
        Create API Key
      </button>
    </div>

    <!-- Error -->
    <div v-if="store.error" class="px-4 py-3 rounded-lg text-sm" style="background: var(--error-bg); color: var(--error-text);">
      {{ store.error }}
    </div>

    <!-- One-time key display (after create) -->
    <div v-if="createdFullKey" class="rounded-lg p-4 space-y-3" style="background: var(--warn-bg); border: 1px solid var(--warn-border, var(--border));">
      <div class="flex items-start gap-2">
        <svg class="w-5 h-5 shrink-0 mt-0.5" style="color: var(--warn-text);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <div>
          <p class="text-sm font-semibold" style="color: var(--warn-text);">Copy your API key now</p>
          <p class="text-xs mt-0.5" style="color: var(--warn-text); opacity: 0.8;">This key will not be shown again. If you lose it, you'll need to create a new one.</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <code class="flex-1 px-3 py-2 rounded text-xs font-mono break-all" style="background: var(--surface); color: var(--text-1); border: 1px solid var(--border);">
          {{ createdFullKey }}
        </code>
        <button
          class="px-3 py-2 text-xs font-medium rounded-lg transition-colors shrink-0"
          :style="keyCopied ? 'background: var(--success-bg); color: var(--success-text);' : 'background: var(--surface-alt); color: var(--text-2); border: 1px solid var(--border);'"
          @click="copyKey(createdFullKey!)"
        >
          {{ keyCopied ? 'Copied!' : 'Copy' }}
        </button>
      </div>
      <button class="text-xs underline" style="color: var(--warn-text); opacity: 0.8;" @click="createdFullKey = null">Dismiss</button>
    </div>

    <!-- Rotated key display -->
    <div v-if="rotatedFullKey" class="rounded-lg p-4 space-y-3" style="background: var(--info-bg); border: 1px solid var(--info-border, var(--border));">
      <div class="flex items-start gap-2">
        <svg class="w-5 h-5 shrink-0 mt-0.5" style="color: var(--info-text);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        <div>
          <p class="text-sm font-semibold" style="color: var(--info-text);">Key rotated — copy your new key</p>
          <p class="text-xs mt-0.5" style="color: var(--info-text); opacity: 0.8;">The old key remains valid for 5 minutes. Copy the new key now.</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <code class="flex-1 px-3 py-2 rounded text-xs font-mono break-all" style="background: var(--surface); color: var(--text-1); border: 1px solid var(--border);">
          {{ rotatedFullKey }}
        </code>
        <button
          class="px-3 py-2 text-xs font-medium rounded-lg transition-colors shrink-0"
          :style="keyCopied ? 'background: var(--success-bg); color: var(--success-text);' : 'background: var(--surface-alt); color: var(--text-2); border: 1px solid var(--border);'"
          @click="copyKey(rotatedFullKey!)"
        >
          {{ keyCopied ? 'Copied!' : 'Copy' }}
        </button>
      </div>
      <button class="text-xs underline" style="color: var(--info-text); opacity: 0.8;" @click="rotatedFullKey = null">Dismiss</button>
    </div>

    <!-- Tab switch: Active / Revoked -->
    <div class="flex gap-4 border-b" style="border-color: var(--border);">
      <button
        class="pb-2 text-sm font-medium transition-colors border-b-2"
        :style="!showRevoked ? 'border-color: var(--brand-primary); color: var(--text-1);' : 'border-color: transparent; color: var(--text-3);'"
        @click="showRevoked = false"
      >
        Active ({{ store.activeKeys.length }})
      </button>
      <button
        class="pb-2 text-sm font-medium transition-colors border-b-2"
        :style="showRevoked ? 'border-color: var(--brand-primary); color: var(--text-1);' : 'border-color: transparent; color: var(--text-3);'"
        @click="showRevoked = true"
      >
        Revoked ({{ store.revokedKeys.length }})
      </button>
    </div>

    <!-- Loading -->
    <div v-if="store.isLoading" class="text-center py-12">
      <div class="skeleton w-full h-16 rounded-lg mb-3" />
      <div class="skeleton w-full h-16 rounded-lg mb-3" />
      <div class="skeleton w-full h-16 rounded-lg" />
    </div>

    <!-- Empty state -->
    <div v-else-if="displayedKeys.length === 0" class="text-center py-16">
      <svg class="w-12 h-12 mx-auto mb-3" style="color: var(--text-3);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
      </svg>
      <p class="text-sm font-medium" style="color: var(--text-2);">
        {{ showRevoked ? 'No revoked API keys' : 'No API keys yet' }}
      </p>
      <p v-if="!showRevoked" class="text-xs mt-1" style="color: var(--text-3);">
        Create an API key to allow external tools to access Sentora data.
      </p>
    </div>

    <!-- Key list -->
    <div v-else class="space-y-3">
      <div
        v-for="key in displayedKeys"
        :key="key.id"
        class="rounded-lg p-4 transition-colors"
        style="background: var(--surface); border: 1px solid var(--border);"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <h3 class="text-sm font-semibold truncate" style="color: var(--text-1);">{{ key.name }}</h3>
              <span
                class="text-[10px] font-medium px-1.5 py-0.5 rounded-full"
                :style="key.is_active ? 'background: var(--success-bg); color: var(--success-text);' : 'background: var(--error-bg); color: var(--error-text);'"
              >
                {{ key.is_active ? 'Active' : 'Revoked' }}
              </span>
              <span v-if="key.expires_at && new Date(key.expires_at) < new Date()" class="text-[10px] font-medium px-1.5 py-0.5 rounded-full" style="background: var(--error-bg); color: var(--error-text);">
                Expired
              </span>
            </div>
            <code class="text-xs font-mono mt-1 block" style="color: var(--text-3);">{{ key.key_prefix }}...</code>
            <p v-if="key.description" class="text-xs mt-1" style="color: var(--text-3);">{{ key.description }}</p>

            <!-- Scopes -->
            <div class="flex flex-wrap gap-1 mt-2">
              <span
                v-for="scope in key.scopes"
                :key="scope"
                class="text-[10px] font-medium px-1.5 py-0.5 rounded"
                :style="scopeColor(scope)"
              >
                {{ scope }}
              </span>
            </div>

            <!-- Meta -->
            <div class="flex flex-wrap gap-4 mt-2 text-[11px]" style="color: var(--text-3);">
              <span>Created {{ formatDate(key.created_at) }} by {{ key.created_by }}</span>
              <span>Last used: {{ timeAgo(key.last_used_at) }}</span>
              <span v-if="key.last_used_ip">IP: {{ key.last_used_ip }}</span>
              <span>{{ key.rate_limit_per_minute }}/min, {{ key.rate_limit_per_hour }}/hr</span>
              <span v-if="key.expires_at">Expires: {{ formatDate(key.expires_at) }}</span>
            </div>
          </div>

          <!-- Actions -->
          <div v-if="key.is_active" class="flex items-center gap-1.5 shrink-0">
            <button
              class="px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors"
              style="background: var(--surface-alt); color: var(--text-2); border: 1px solid var(--border);"
              @click="openEdit(key)"
            >Edit</button>
            <button
              class="px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors"
              style="background: var(--info-bg); color: var(--info-text);"
              @click="confirmAction = 'rotate'; confirmTarget = key"
            >Rotate</button>
            <button
              class="px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors"
              style="background: var(--error-bg); color: var(--error-text);"
              @click="confirmAction = 'revoke'; confirmTarget = key"
            >Revoke</button>
          </div>
          <div v-else class="text-xs shrink-0" style="color: var(--text-3);">
            <span v-if="key.revoked_at">Revoked {{ formatDate(key.revoked_at) }}</span>
            <span v-if="key.revoked_by"> by {{ key.revoked_by }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Dialog -->
    <Teleport to="body">
      <div v-if="showCreate" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="fixed inset-0 bg-black/50" @click="showCreate = false" />
        <div class="relative w-full max-w-lg rounded-xl shadow-xl p-6 space-y-4" style="background: var(--surface); border: 1px solid var(--border);">
          <h3 class="text-base font-semibold" style="color: var(--heading);">Create API Key</h3>

          <div>
            <label class="block text-xs font-medium mb-1" style="color: var(--text-2);">Name *</label>
            <input
              v-model="createForm.name"
              class="w-full px-3 py-2 rounded-lg text-sm"
              style="background: var(--surface-alt); color: var(--text-1); border: 1px solid var(--border);"
              placeholder="e.g. Splunk Integration"
            />
          </div>

          <div>
            <label class="block text-xs font-medium mb-1" style="color: var(--text-2);">Description</label>
            <input
              v-model="createForm.description"
              class="w-full px-3 py-2 rounded-lg text-sm"
              style="background: var(--surface-alt); color: var(--text-1); border: 1px solid var(--border);"
              placeholder="Optional description"
            />
          </div>

          <!-- Scopes -->
          <div>
            <div class="flex items-center justify-between mb-1">
              <label class="text-xs font-medium" style="color: var(--text-2);">Scopes *</label>
              <button
                class="text-[10px] font-medium px-2 py-0.5 rounded transition-colors"
                :style="allReadSelected(createForm.scopes) ? 'background: var(--info-bg); color: var(--info-text);' : 'background: var(--surface-alt); color: var(--text-3);'"
                @click="createForm.scopes = selectAllRead(createForm.scopes)"
              >
                {{ allReadSelected(createForm.scopes) ? 'Deselect All Read' : 'Select All Read' }}
              </button>
            </div>
            <div class="grid grid-cols-2 gap-1.5 max-h-48 overflow-y-auto">
              <label
                v-for="(desc, scope) in AVAILABLE_SCOPES"
                :key="scope"
                class="flex items-start gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors text-xs"
                style="background: var(--surface-alt);"
              >
                <input
                  type="checkbox"
                  :checked="createForm.scopes.includes(scope)"
                  class="mt-0.5 rounded"
                  @change="createForm.scopes = toggleScope(createForm.scopes, scope)"
                />
                <div>
                  <span class="font-medium" style="color: var(--text-1);">{{ scope }}</span>
                  <p class="text-[10px] leading-tight" style="color: var(--text-3);">{{ desc }}</p>
                </div>
              </label>
            </div>
          </div>

          <!-- Rate limits -->
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium mb-1" style="color: var(--text-2);">Requests / minute</label>
              <input
                v-model.number="createForm.rate_limit_per_minute"
                type="number"
                min="1"
                max="10000"
                class="w-full px-3 py-2 rounded-lg text-sm"
                style="background: var(--surface-alt); color: var(--text-1); border: 1px solid var(--border);"
              />
            </div>
            <div>
              <label class="block text-xs font-medium mb-1" style="color: var(--text-2);">Requests / hour</label>
              <input
                v-model.number="createForm.rate_limit_per_hour"
                type="number"
                min="1"
                max="100000"
                class="w-full px-3 py-2 rounded-lg text-sm"
                style="background: var(--surface-alt); color: var(--text-1); border: 1px solid var(--border);"
              />
            </div>
          </div>

          <!-- Expiry -->
          <div>
            <label class="block text-xs font-medium mb-1" style="color: var(--text-2);">Expiry (optional)</label>
            <input
              v-model="createForm.expires_at"
              type="datetime-local"
              class="w-full px-3 py-2 rounded-lg text-sm"
              style="background: var(--surface-alt); color: var(--text-1); border: 1px solid var(--border);"
            />
          </div>

          <div class="flex justify-end gap-2 pt-2">
            <button
              class="px-4 py-2 text-sm rounded-lg transition-colors"
              style="color: var(--text-2);"
              @click="showCreate = false"
            >Cancel</button>
            <button
              class="px-4 py-2 text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
              style="background: var(--brand-primary); color: white;"
              :disabled="!createForm.name || createForm.scopes.length === 0"
              @click="handleCreate"
            >Create Key</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Edit Dialog -->
    <Teleport to="body">
      <div v-if="showEdit" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="fixed inset-0 bg-black/50" @click="showEdit = false" />
        <div class="relative w-full max-w-lg rounded-xl shadow-xl p-6 space-y-4" style="background: var(--surface); border: 1px solid var(--border);">
          <h3 class="text-base font-semibold" style="color: var(--heading);">Edit API Key</h3>

          <div>
            <label class="block text-xs font-medium mb-1" style="color: var(--text-2);">Name</label>
            <input
              v-model="editForm.name"
              class="w-full px-3 py-2 rounded-lg text-sm"
              style="background: var(--surface-alt); color: var(--text-1); border: 1px solid var(--border);"
            />
          </div>

          <div>
            <label class="block text-xs font-medium mb-1" style="color: var(--text-2);">Description</label>
            <input
              v-model="editForm.description"
              class="w-full px-3 py-2 rounded-lg text-sm"
              style="background: var(--surface-alt); color: var(--text-1); border: 1px solid var(--border);"
            />
          </div>

          <!-- Scopes -->
          <div>
            <div class="flex items-center justify-between mb-1">
              <label class="text-xs font-medium" style="color: var(--text-2);">Scopes</label>
              <button
                class="text-[10px] font-medium px-2 py-0.5 rounded transition-colors"
                :style="allReadSelected(editForm.scopes) ? 'background: var(--info-bg); color: var(--info-text);' : 'background: var(--surface-alt); color: var(--text-3);'"
                @click="editForm.scopes = selectAllRead(editForm.scopes)"
              >
                {{ allReadSelected(editForm.scopes) ? 'Deselect All Read' : 'Select All Read' }}
              </button>
            </div>
            <div class="grid grid-cols-2 gap-1.5 max-h-48 overflow-y-auto">
              <label
                v-for="(desc, scope) in AVAILABLE_SCOPES"
                :key="scope"
                class="flex items-start gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors text-xs"
                style="background: var(--surface-alt);"
              >
                <input
                  type="checkbox"
                  :checked="editForm.scopes.includes(scope)"
                  class="mt-0.5 rounded"
                  @change="editForm.scopes = toggleScope(editForm.scopes, scope)"
                />
                <div>
                  <span class="font-medium" style="color: var(--text-1);">{{ scope }}</span>
                  <p class="text-[10px] leading-tight" style="color: var(--text-3);">{{ desc }}</p>
                </div>
              </label>
            </div>
          </div>

          <!-- Rate limits -->
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium mb-1" style="color: var(--text-2);">Requests / minute</label>
              <input
                v-model.number="editForm.rate_limit_per_minute"
                type="number"
                min="1"
                max="10000"
                class="w-full px-3 py-2 rounded-lg text-sm"
                style="background: var(--surface-alt); color: var(--text-1); border: 1px solid var(--border);"
              />
            </div>
            <div>
              <label class="block text-xs font-medium mb-1" style="color: var(--text-2);">Requests / hour</label>
              <input
                v-model.number="editForm.rate_limit_per_hour"
                type="number"
                min="1"
                max="100000"
                class="w-full px-3 py-2 rounded-lg text-sm"
                style="background: var(--surface-alt); color: var(--text-1); border: 1px solid var(--border);"
              />
            </div>
          </div>

          <div class="flex justify-end gap-2 pt-2">
            <button
              class="px-4 py-2 text-sm rounded-lg transition-colors"
              style="color: var(--text-2);"
              @click="showEdit = false"
            >Cancel</button>
            <button
              class="px-4 py-2 text-sm font-medium rounded-lg transition-colors"
              style="background: var(--brand-primary); color: white;"
              @click="handleEdit"
            >Save Changes</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Confirm Dialog (Revoke / Rotate) -->
    <Teleport to="body">
      <div v-if="confirmAction" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="fixed inset-0 bg-black/50" @click="confirmAction = null; confirmTarget = null" />
        <div class="relative w-full max-w-sm rounded-xl shadow-xl p-6 space-y-4" style="background: var(--surface); border: 1px solid var(--border);">
          <h3 class="text-base font-semibold" style="color: var(--heading);">
            {{ confirmAction === 'revoke' ? 'Revoke API Key' : 'Rotate API Key' }}
          </h3>
          <p class="text-sm" style="color: var(--text-2);">
            <template v-if="confirmAction === 'revoke'">
              Are you sure you want to revoke <strong>{{ confirmTarget?.name }}</strong>?
              This action is immediate and cannot be undone. All requests using this key will be rejected.
            </template>
            <template v-else>
              Rotate <strong>{{ confirmTarget?.name }}</strong>?
              A new key will be generated with the same scopes and limits. The old key remains valid for 5 minutes.
            </template>
          </p>
          <div class="flex justify-end gap-2">
            <button
              class="px-4 py-2 text-sm rounded-lg transition-colors"
              style="color: var(--text-2);"
              @click="confirmAction = null; confirmTarget = null"
            >Cancel</button>
            <button
              class="px-4 py-2 text-sm font-medium rounded-lg transition-colors"
              :style="confirmAction === 'revoke' ? 'background: var(--error-bg); color: var(--error-text);' : 'background: var(--info-bg); color: var(--info-text);'"
              @click="handleConfirmAction"
            >
              {{ confirmAction === 'revoke' ? 'Revoke Key' : 'Rotate Key' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
