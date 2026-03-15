<!--
  User Management view — admin-only.
  List users, change roles, enable/disable, delete.
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/useAuthStore'
import * as authApi from '@/api/auth'
import type { UserInfo } from '@/types/auth'

const auth = useAuthStore()
const users = ref<UserInfo[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const search = ref('')

// Confirm delete modal
const confirmDelete = ref<string | null>(null)

const filteredUsers = computed(() => {
  const q = search.value.toLowerCase()
  if (!q) return users.value
  return users.value.filter(u =>
    u.username.toLowerCase().includes(q) ||
    u.email.toLowerCase().includes(q) ||
    u.role.includes(q),
  )
})

async function fetchUsers() {
  loading.value = true
  error.value = null
  try {
    const resp = await authApi.listUsers()
    users.value = resp.users
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load users'
  } finally {
    loading.value = false
  }
}

async function changeRole(username: string, role: string) {
  try {
    const updated = await authApi.updateUserRole(username, role)
    const idx = users.value.findIndex(u => u.username === username)
    if (idx >= 0) users.value[idx] = updated
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to update role'
  }
}

async function toggleDisabled(username: string, disabled: boolean) {
  try {
    const updated = await authApi.updateUserDisabled(username, disabled)
    const idx = users.value.findIndex(u => u.username === username)
    if (idx >= 0) users.value[idx] = updated
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to update user'
  }
}

async function changeStatus(username: string, status: string) {
  try {
    const updated = await authApi.updateUserStatus(username, status)
    const idx = users.value.findIndex(u => u.username === username)
    if (idx >= 0) users.value[idx] = updated
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to update status'
  }
}

async function revokeSessions(username: string) {
  try {
    await authApi.adminRevokeSessions(username)
    error.value = null
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to revoke sessions'
  }
}

const statusBadge: Record<string, string> = {
  active: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  invited: 'bg-blue-50 text-blue-700 border-blue-200',
  suspended: 'bg-amber-50 text-amber-700 border-amber-200',
  deactivated: 'bg-red-50 text-red-600 border-red-200',
  deleted: 'bg-gray-50 text-gray-500 border-gray-200',
}

async function handleDelete(username: string) {
  try {
    await authApi.deleteUser(username)
    users.value = users.value.filter(u => u.username !== username)
    confirmDelete.value = null
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to delete user'
  }
}

const roleBadge: Record<string, string> = {
  super_admin: 'bg-purple-500/10 text-purple-500 border-purple-500/20',
  admin: 'bg-red-50 text-red-700 border-red-200',
  analyst: 'bg-amber-50 text-amber-700 border-amber-200',
  viewer: 'badge-neutral-muted border',
}

onMounted(fetchUsers)
</script>

<template>
  <div class="p-6 max-w-5xl mx-auto">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h2 class="text-lg font-semibold" style="color: var(--heading);">User Management</h2>
        <p class="text-sm mt-0.5" style="color: var(--text-3);">Manage user accounts, roles, and access</p>
      </div>
      <span class="text-xs" style="color: var(--text-3);">{{ users.length }} user{{ users.length !== 1 ? 's' : '' }}</span>
    </div>

    <!-- Error -->
    <div
      v-if="error"
      class="mb-4 px-3 py-2 text-sm rounded-lg"
      style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);"
      role="alert"
    >
      {{ error }}
      <button @click="error = null" class="ml-2 text-red-500 hover:text-red-700">&times;</button>
    </div>

    <!-- Search -->
    <div class="mb-4">
      <input
        v-model="search"
        type="text"
        placeholder="Search users…"
        class="w-full max-w-xs px-3 py-2 text-sm rounded-lg outline-none transition focus:ring-1 focus:ring-indigo-400"
        style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
      />
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-12">
      <svg class="animate-spin w-6 h-6 text-indigo-500 mx-auto mb-2" fill="none" viewBox="0 0 24 24" aria-hidden="true">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
      </svg>
      <p class="text-sm" style="color: var(--text-3);">Loading users…</p>
    </div>

    <!-- Table -->
    <div v-else class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
      <table class="w-full text-sm">
        <thead>
          <tr style="background: var(--surface-inset); border-bottom: 1px solid var(--border);">
            <th class="text-left px-4 py-3 text-xs font-medium uppercase tracking-wider" style="color: var(--text-3);" scope="col">User</th>
            <th class="text-left px-4 py-3 text-xs font-medium uppercase tracking-wider" style="color: var(--text-3);" scope="col">Role</th>
            <th class="text-center px-4 py-3 text-xs font-medium uppercase tracking-wider" style="color: var(--text-3);" scope="col">2FA</th>
            <th class="text-center px-4 py-3 text-xs font-medium uppercase tracking-wider" style="color: var(--text-3);" scope="col">Status</th>
            <th class="text-right px-4 py-3 text-xs font-medium uppercase tracking-wider" style="color: var(--text-3);" scope="col">Actions</th>
          </tr>
        </thead>
        <tbody style="border-color: var(--border-light);">
          <tr v-for="u in filteredUsers" :key="u.username" class="transition-colors" style="border-bottom: 1px solid var(--border-light);">
            <!-- User -->
            <td class="px-4 py-3">
              <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                  :class="u.disabled ? '' : 'bg-indigo-500/10'" style="background: var(--surface-hover);"
                >
                  <span class="text-xs font-semibold uppercase" :class="u.disabled ? 'text-gray-400' : 'text-indigo-500'">
                    {{ u.username.charAt(0) }}
                  </span>
                </div>
                <div class="min-w-0">
                  <p class="text-sm font-medium truncate" :class="{ 'line-through opacity-50': u.disabled }" style="color: var(--text-1);">
                    {{ u.username }}
                  </p>
                  <p class="text-xs truncate" style="color: var(--text-3);">{{ u.email }}</p>
                </div>
              </div>
            </td>

            <!-- Role dropdown -->
            <td class="px-4 py-3">
              <select
                :value="u.role"
                @change="changeRole(u.username, ($event.target as HTMLSelectElement).value)"
                :disabled="u.username === auth.user?.username"
                class="text-xs font-medium px-2 py-1 rounded-lg border outline-none cursor-pointer disabled:cursor-not-allowed disabled:opacity-60"
                :class="roleBadge[u.role]"
                :aria-label="`Role for ${u.username}`"
              >
                <option value="super_admin">Super Admin</option>
                <option value="admin">Admin</option>
                <option value="analyst">Analyst</option>
                <option value="viewer">Viewer</option>
              </select>
            </td>

            <!-- 2FA -->
            <td class="px-4 py-3 text-center">
              <span
                class="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full"
                :class="u.totp_enabled ? 'bg-emerald-50 text-emerald-700' : 'badge-neutral-muted'"
              >
                <svg v-if="u.totp_enabled" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                {{ u.totp_enabled ? 'Enabled' : 'Off' }}
              </span>
            </td>

            <!-- Status -->
            <td class="px-4 py-3 text-center">
              <select
                :value="u.status || (u.disabled ? 'deactivated' : 'active')"
                @change="changeStatus(u.username, ($event.target as HTMLSelectElement).value)"
                :disabled="u.username === auth.user?.username"
                class="text-xs font-medium px-2 py-1 rounded-lg border outline-none cursor-pointer disabled:cursor-not-allowed disabled:opacity-60"
                :class="statusBadge[u.status || (u.disabled ? 'deactivated' : 'active')]"
                :aria-label="`Status for ${u.username}`"
              >
                <option value="active">Active</option>
                <option value="suspended">Suspended</option>
                <option value="deactivated">Deactivated</option>
              </select>
            </td>

            <!-- Actions -->
            <td class="px-4 py-3 text-right">
              <div class="flex items-center justify-end gap-1">
                <button
                  v-if="u.username !== auth.user?.username"
                  @click="revokeSessions(u.username)"
                  class="p-1.5 rounded-lg hover:text-amber-500 hover:bg-amber-50 transition"
                  style="color: var(--text-3);"
                  :aria-label="`Revoke sessions for ${u.username}`"
                  title="Revoke all sessions"
                >
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                  </svg>
                </button>
                <button
                  v-if="u.username !== auth.user?.username"
                  @click="confirmDelete = u.username"
                  class="p-1.5 rounded-lg hover:text-red-500 hover:bg-red-50 transition"
                  style="color: var(--text-3);"
                  :aria-label="`Delete ${u.username}`"
                  title="Delete user"
                >
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
                <span v-if="u.username === auth.user?.username" class="text-xs italic" style="color: var(--text-3);">you</span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="filteredUsers.length === 0 && !loading" class="text-center py-8">
        <p class="text-sm" style="color: var(--text-3);">No users found</p>
      </div>
    </div>
  </div>

  <!-- Delete confirmation modal -->
  <div v-if="confirmDelete" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4" @click.self="confirmDelete = null">
    <div class="rounded-xl shadow-xl w-full max-w-xs p-5" style="background: var(--surface); border: 1px solid var(--border);" role="dialog" aria-modal="true" aria-label="Confirm delete user">
      <div class="text-center">
        <div class="inline-flex items-center justify-center w-10 h-10 rounded-full bg-red-50 mb-3">
          <svg class="w-5 h-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h3 class="text-sm font-semibold mb-1" style="color: var(--heading);">Delete user</h3>
        <p class="text-sm mb-4" style="color: var(--text-3);">
          Are you sure you want to delete <strong>{{ confirmDelete }}</strong>? This cannot be undone.
        </p>
        <div class="flex gap-2">
          <button
            @click="confirmDelete = null"
            class="flex-1 py-2 px-3 text-sm font-medium rounded-lg transition"
            style="background: var(--badge-bg); color: var(--text-2);"
          >
            Cancel
          </button>
          <button
            @click="handleDelete(confirmDelete!)"
            class="flex-1 py-2 px-3 text-sm font-medium text-white bg-red-500 hover:bg-red-600 rounded-lg transition"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
