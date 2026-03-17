<!--
  Tenant Management view — super_admin only.
  List, create, edit, enable/disable, and delete tenants.
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import * as tenantApi from '@/api/tenants'
import { useAsyncAction } from '@/composables/useAsyncAction'
import type { Tenant, TenantCreatePayload } from '@/api/tenants'

const { execute: guardedExecute } = useAsyncAction()
const tenants = ref<Tenant[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const search = ref('')

// Create modal
const showCreate = ref(false)
const createForm = ref<TenantCreatePayload>({ name: '', slug: '' })
const createError = ref<string | null>(null)
const creating = ref(false)

// Delete confirmation
const confirmDelete = ref<string | null>(null)

const filteredTenants = computed(() => {
  const q = search.value.toLowerCase()
  if (!q) return tenants.value
  return tenants.value.filter(t =>
    t.name.toLowerCase().includes(q) ||
    t.slug.toLowerCase().includes(q) ||
    t.plan.includes(q),
  )
})

async function fetchTenants() {
  loading.value = true
  error.value = null
  try {
    const resp = await tenantApi.listTenants()
    tenants.value = resp.tenants
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load tenants'
  } finally {
    loading.value = false
  }
}

function autoSlug() {
  createForm.value.slug = createForm.value.name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

async function handleCreate() {
  creating.value = true
  createError.value = null
  try {
    const tenant = await tenantApi.createTenant(createForm.value)
    tenants.value.push(tenant)
    showCreate.value = false
    createForm.value = { name: '', slug: '' }
  } catch (err) {
    createError.value = err instanceof Error ? err.message : 'Failed to create tenant'
  } finally {
    creating.value = false
  }
}

async function toggleDisabled(tenant: Tenant) {
  await guardedExecute(async () => {
    try {
    const updated = await tenantApi.updateTenant(tenant.slug, { disabled: !tenant.disabled })
    const idx = tenants.value.findIndex(t => t.slug === tenant.slug)
    if (idx >= 0) tenants.value[idx] = updated
  } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update tenant'
    }
  })
}

async function changePlan(slug: string, plan: string) {
  try {
    const updated = await tenantApi.updateTenant(slug, { plan })
    const idx = tenants.value.findIndex(t => t.slug === slug)
    if (idx >= 0) tenants.value[idx] = updated
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to update plan'
  }
}

async function handleDelete(slug: string) {
  await guardedExecute(async () => {
    try {
    await tenantApi.deleteTenant(slug)
    tenants.value = tenants.value.filter(t => t.slug !== slug)
    confirmDelete.value = null
  } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to delete tenant'
    }
  })
}

onMounted(fetchTenants)
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold" style="color: var(--heading);">Tenant Management</h1>
      <button
        class="px-4 py-2 bg-[var(--brand-primary)] text-white rounded-lg hover:opacity-90 transition-colors text-sm font-medium"
        aria-label="Create new tenant"
        @click="showCreate = true"
      >
        + New Tenant
      </button>
    </div>

    <!-- Error banner -->
    <div v-if="error" class="mb-4 p-3 rounded-lg text-sm" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
      {{ error }}
      <button class="ml-2 underline" @click="error = null">dismiss</button>
    </div>

    <!-- Search -->
    <div class="mb-4">
      <input
        v-model="search"
        type="text"
        placeholder="Search tenants..."
        class="w-full max-w-md px-3 py-2 rounded-lg text-sm"
        style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
        aria-label="Search tenants"
      />
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-12" style="color: var(--text-3);">Loading tenants...</div>

    <!-- Table -->
    <div v-else-if="filteredTenants.length" class="overflow-x-auto rounded-lg" style="border: 1px solid var(--border);">
      <table class="min-w-full divide-y" style="border-color: var(--border);">
        <thead style="background: var(--surface-inset);">
          <tr>
            <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Name</th>
            <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Slug</th>
            <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Database</th>
            <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Plan</th>
            <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Status</th>
            <th class="px-4 py-3 text-left text-xs font-medium uppercase" style="color: var(--text-3);">Created</th>
            <th class="px-4 py-3 text-right text-xs font-medium uppercase" style="color: var(--text-3);">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y" style="background: var(--surface); border-color: var(--border);">
          <tr v-for="tenant in filteredTenants" :key="tenant.slug">
            <td class="px-4 py-3 text-sm font-medium" style="color: var(--text-1);">{{ tenant.name }}</td>
            <td class="px-4 py-3 text-sm font-mono" style="color: var(--text-3);">{{ tenant.slug }}</td>
            <td class="px-4 py-3 text-sm font-mono" style="color: var(--text-3);">{{ tenant.database_name }}</td>
            <td class="px-4 py-3 text-sm">
              <select
                :value="tenant.plan"
                class="bg-transparent rounded px-2 py-1 text-sm"
                style="border: 1px solid var(--border); color: var(--text-2);"
                :aria-label="`Plan for ${tenant.name}`"
                @change="changePlan(tenant.slug, ($event.target as HTMLSelectElement).value)"
              >
                <option value="standard">Standard</option>
                <option value="professional">Professional</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </td>
            <td class="px-4 py-3 text-sm">
              <span
                :class="tenant.disabled
                  ? 'bg-[var(--error-bg)] text-[var(--error-text)]'
                  : 'bg-[var(--success-bg)] text-[var(--success-text)]'"
                class="inline-flex px-2 py-0.5 text-xs font-medium rounded-full"
              >
                {{ tenant.disabled ? 'Disabled' : 'Active' }}
              </span>
            </td>
            <td class="px-4 py-3 text-sm" style="color: var(--text-3);">
              {{ new Date(tenant.created_at).toLocaleDateString() }}
            </td>
            <td class="px-4 py-3 text-sm text-right space-x-2">
              <button
                class="text-[var(--info-text)] hover:underline text-sm"
                :aria-label="tenant.disabled ? `Enable ${tenant.name}` : `Disable ${tenant.name}`"
                @click="toggleDisabled(tenant)"
              >
                {{ tenant.disabled ? 'Enable' : 'Disable' }}
              </button>
              <button
                class="text-[var(--error-text)] hover:underline text-sm"
                :aria-label="`Delete ${tenant.name}`"
                @click="confirmDelete = tenant.slug"
              >
                Delete
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Empty state -->
    <div v-else class="text-center py-12" style="color: var(--text-3);">
      <p class="text-lg mb-2">No tenants found</p>
      <p class="text-sm">Create your first tenant to get started with multi-tenancy.</p>
    </div>

    <!-- Create Modal -->
    <div v-if="showCreate" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="showCreate = false">
      <div class="rounded-xl shadow-xl p-6 w-full max-w-md" style="background: var(--surface);" role="dialog" aria-label="Create tenant">
        <h2 class="text-lg font-semibold mb-4" style="color: var(--heading);">Create Tenant</h2>
        <div v-if="createError" class="mb-3 p-2 rounded text-sm" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);" role="alert">
          {{ createError }}
        </div>
        <form @submit.prevent="handleCreate" class="space-y-4">
          <div>
            <label class="block text-sm font-medium mb-1" style="color: var(--text-2);">Name</label>
            <input
              v-model="createForm.name"
              type="text"
              required
              class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              placeholder="Acme Corporation"
              @input="autoSlug"
            />
          </div>
          <div>
            <label class="block text-sm font-medium mb-1" style="color: var(--text-2);">Slug</label>
            <input
              v-model="createForm.slug"
              type="text"
              required
              pattern="[a-z0-9][a-z0-9-]*[a-z0-9]"
              class="w-full px-3 py-2 rounded-lg text-sm font-mono" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              placeholder="acme-corporation"
            />
            <p class="mt-1 text-xs" style="color: var(--text-3);">Lowercase letters, numbers, and hyphens only.</p>
          </div>
          <div>
            <label class="block text-sm font-medium mb-1" style="color: var(--text-2);">Plan</label>
            <select
              v-model="createForm.plan"
              class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
            >
              <option value="">Standard (default)</option>
              <option value="professional">Professional</option>
              <option value="enterprise">Enterprise</option>
            </select>
          </div>
          <div class="flex justify-end gap-3 pt-2">
            <button type="button" class="px-4 py-2 text-sm rounded-lg" style="color: var(--text-2);" @click="showCreate = false">Cancel</button>
            <button type="submit" :disabled="creating" class="px-4 py-2 text-sm bg-[var(--brand-primary)] text-white rounded-lg hover:opacity-90 disabled:opacity-50">
              {{ creating ? 'Creating...' : 'Create Tenant' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div v-if="confirmDelete" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="confirmDelete = null">
      <div class="rounded-xl shadow-xl p-6 w-full max-w-sm" style="background: var(--surface);" role="alertdialog" aria-label="Confirm delete tenant">
        <h2 class="text-lg font-semibold mb-2" style="color: var(--heading);">Delete Tenant</h2>
        <p class="text-sm mb-4" style="color: var(--text-2);">
          Are you sure you want to delete tenant <strong class="font-mono">{{ confirmDelete }}</strong>? This action cannot be undone and will remove all tenant data.
        </p>
        <div class="flex justify-end gap-3">
          <button class="px-4 py-2 text-sm rounded-lg" style="color: var(--text-2);" @click="confirmDelete = null">Cancel</button>
          <button class="px-4 py-2 text-sm bg-[var(--error-text)] text-white rounded-lg hover:opacity-90" @click="handleDelete(confirmDelete!)">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>
