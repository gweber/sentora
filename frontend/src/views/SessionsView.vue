<!--
  Session Management view — shows all active sessions (devices) for the current user.
  Allows revoking individual sessions or all other sessions.
  Also includes password change functionality.
-->
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import * as authApi from '@/api/auth'
import { useAsyncAction } from '@/composables/useAsyncAction'
import type { SessionInfo, PasswordPolicy } from '@/types/auth'

const { execute: guardedExecute } = useAsyncAction()
const sessions = ref<SessionInfo[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const passwordPolicy = ref<PasswordPolicy | null>(null)

// Password change state
const showPasswordForm = ref(false)
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const passwordError = ref<string | null>(null)
const passwordSuccess = ref(false)
const savingPassword = ref(false)

const passwordsMatch = computed(() => newPassword.value === confirmPassword.value)
const passwordValid = computed(() => {
  const p = newPassword.value
  if (!passwordPolicy.value) return p.length >= 8
  const pol = passwordPolicy.value
  if (p.length < pol.min_length) return false
  if (pol.require_uppercase && !/[A-Z]/.test(p)) return false
  if (pol.require_lowercase && !/[a-z]/.test(p)) return false
  if (pol.require_digit && !/\d/.test(p)) return false
  if (pol.require_special && !/[^A-Za-z0-9]/.test(p)) return false
  return true
})

async function fetchSessions() {
  loading.value = true
  error.value = null
  try {
    const resp = await authApi.listSessions()
    sessions.value = resp.sessions
  } catch {
    error.value = 'Failed to load sessions'
  } finally {
    loading.value = false
  }
}

async function fetchPasswordPolicy() {
  try {
    passwordPolicy.value = await authApi.getPasswordPolicy()
  } catch {
    // Non-critical
  }
}

async function revokeSession(sessionId: string) {
  await guardedExecute(async () => {
    try {
    await authApi.revokeSession(sessionId)
    sessions.value = sessions.value.filter(s => s.id !== sessionId)
    } catch {
      error.value = 'Failed to revoke session'
    }
  })
}

async function revokeOtherSessions() {
  await guardedExecute(async () => {
    try {
    await authApi.revokeOtherSessions()
    sessions.value = sessions.value.filter(s => s.is_current)
    } catch {
      error.value = 'Failed to revoke sessions'
    }
  })
}

async function handlePasswordChange() {
  passwordError.value = null
  passwordSuccess.value = false
  if (!passwordsMatch.value || !passwordValid.value) return

  savingPassword.value = true
  try {
    await authApi.changePassword({
      current_password: currentPassword.value,
      new_password: newPassword.value,
    })
    passwordSuccess.value = true
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    showPasswordForm.value = false
    // Refresh sessions — others will have been revoked
    await fetchSessions()
  } catch (err: unknown) {
    const axiosErr = err as { response?: { data?: { detail?: string } } }
    passwordError.value = axiosErr?.response?.data?.detail || 'Failed to change password'
  } finally {
    savingPassword.value = false
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

function parseUserAgent(ua: string): string {
  if (ua.includes('Chrome') && !ua.includes('Edg')) return 'Chrome'
  if (ua.includes('Firefox')) return 'Firefox'
  if (ua.includes('Safari') && !ua.includes('Chrome')) return 'Safari'
  if (ua.includes('Edg')) return 'Edge'
  if (ua.includes('curl')) return 'curl'
  if (ua.includes('python')) return 'Python'
  return ua.slice(0, 40)
}

function getDeviceIcon(ua: string): string {
  if (ua.includes('Mobile') || ua.includes('Android') || ua.includes('iPhone')) return '📱'
  if (ua.includes('Tablet') || ua.includes('iPad')) return '📱'
  return '💻'
}

onMounted(() => {
  fetchSessions()
  fetchPasswordPolicy()
})
</script>

<template>
  <div class="sessions-page">
    <!-- Header -->
    <div class="page-header">
      <div>
        <h1>Account Security</h1>
        <p class="text-muted">Manage your active sessions and security settings</p>
      </div>
    </div>

    <!-- Password change section -->
    <section class="card section-card">
      <div class="section-header" @click="showPasswordForm = !showPasswordForm">
        <h2>Change Password</h2>
        <button class="btn btn-ghost btn-sm">
          {{ showPasswordForm ? 'Cancel' : 'Change' }}
        </button>
      </div>

      <div v-if="showPasswordForm" class="password-form">
        <div v-if="passwordPolicy" class="policy-hints">
          <p class="text-muted">Password requirements:</p>
          <ul>
            <li :class="{ met: newPassword.length >= passwordPolicy.min_length }">
              At least {{ passwordPolicy.min_length }} characters
            </li>
            <li v-if="passwordPolicy.require_uppercase" :class="{ met: /[A-Z]/.test(newPassword) }">
              One uppercase letter
            </li>
            <li v-if="passwordPolicy.require_lowercase" :class="{ met: /[a-z]/.test(newPassword) }">
              One lowercase letter
            </li>
            <li v-if="passwordPolicy.require_digit" :class="{ met: /\d/.test(newPassword) }">
              One digit
            </li>
            <li v-if="passwordPolicy.require_special" :class="{ met: /[^A-Za-z0-9]/.test(newPassword) }">
              One special character
            </li>
            <li v-if="passwordPolicy.history_count > 0">
              Cannot reuse last {{ passwordPolicy.history_count }} passwords
            </li>
          </ul>
        </div>

        <div class="form-group">
          <label>Current Password</label>
          <input v-model="currentPassword" type="password" class="input" autocomplete="current-password" />
        </div>
        <div class="form-group">
          <label>New Password</label>
          <input v-model="newPassword" type="password" class="input" autocomplete="new-password" />
        </div>
        <div class="form-group">
          <label>Confirm New Password</label>
          <input v-model="confirmPassword" type="password" class="input" autocomplete="new-password" />
          <p v-if="confirmPassword && !passwordsMatch" class="field-error">Passwords do not match</p>
        </div>

        <div v-if="passwordError" class="alert alert-error">{{ passwordError }}</div>
        <div v-if="passwordSuccess" class="alert alert-success">
          Password changed successfully. Other sessions have been signed out.
        </div>

        <button
          class="btn btn-primary"
          :disabled="!passwordsMatch || !passwordValid || !currentPassword || savingPassword"
          @click="handlePasswordChange"
        >
          {{ savingPassword ? 'Changing...' : 'Change Password' }}
        </button>
      </div>
    </section>

    <!-- Active sessions -->
    <section class="card section-card">
      <div class="section-header">
        <h2>Active Sessions</h2>
        <button
          v-if="sessions.length > 1"
          class="btn btn-ghost btn-sm btn-danger-text"
          @click="revokeOtherSessions"
        >
          Sign out all other sessions
        </button>
      </div>

      <div v-if="loading" class="loading-state">Loading sessions...</div>
      <div v-else-if="error" class="alert alert-error">{{ error }}</div>
      <div v-else class="sessions-list">
        <div
          v-for="session in sessions"
          :key="session.id"
          class="session-item"
          :class="{ 'session-current': session.is_current }"
        >
          <div class="session-icon">{{ getDeviceIcon(session.user_agent) }}</div>
          <div class="session-details">
            <div class="session-device">
              <span class="device-name">{{ parseUserAgent(session.user_agent) }}</span>
              <span v-if="session.is_current" class="badge badge-current">This device</span>
            </div>
            <div class="session-meta text-muted">
              <span>{{ session.ip_address }}</span>
              <span class="separator">·</span>
              <span>Last active {{ formatDate(session.last_active_at) }}</span>
            </div>
            <div class="session-meta text-muted">
              <span>Created {{ formatDate(session.created_at) }}</span>
            </div>
          </div>
          <button
            v-if="!session.is_current"
            class="btn btn-ghost btn-sm btn-danger-text"
            @click="revokeSession(session.id)"
          >
            Revoke
          </button>
        </div>

        <div v-if="sessions.length === 0" class="empty-state">
          No active sessions found
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.sessions-page {
  max-width: 720px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.page-header h1 {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0;
}

.section-card {
  padding: 1.25rem;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
}

.section-header h2 {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0;
}

.password-form {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.policy-hints {
  padding: 0.75rem;
  background: var(--color-surface-alt);
  border-radius: 0.5rem;
  font-size: 0.85rem;
}

.policy-hints ul {
  margin: 0.25rem 0 0;
  padding-left: 1.25rem;
}

.policy-hints li {
  color: var(--color-text-tertiary);
}

.policy-hints li.met {
  color: var(--color-success);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.form-group label {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--color-text-secondary);
}

.field-error {
  color: var(--color-error);
  font-size: 0.8rem;
  margin: 0;
}

.sessions-list {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 0.5rem;
  background: var(--color-surface-alt);
}

.session-current {
  border: 1px solid var(--color-brand-primary);
}

.session-icon {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.session-details {
  flex: 1;
  min-width: 0;
}

.session-device {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.device-name {
  font-weight: 500;
}

.badge-current {
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 99px;
  background: var(--color-brand-primary);
  color: white;
}

.session-meta {
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.separator {
  margin: 0 0.1rem;
}

.btn-danger-text {
  color: var(--color-error);
}

.loading-state, .empty-state {
  padding: 2rem;
  text-align: center;
  color: var(--color-text-tertiary);
}

.alert {
  padding: 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.85rem;
}

.alert-error {
  background: var(--color-error-bg, #fef2f2);
  color: var(--color-error);
}

.alert-success {
  background: var(--color-success-bg, #f0fdf4);
  color: var(--color-success);
}
</style>
