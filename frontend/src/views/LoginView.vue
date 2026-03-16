<!--
  Login / Register view — full-screen centered card.
  Toggles between login and register mode.
  Shows TOTP modal for 2FA setup (register) and verification (login).
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/useAuthStore'
import { useBranding } from '@/composables/useBranding'
import * as authApi from '@/api/auth'
import TotpModal from '@/components/TotpModal.vue'

const router = useRouter()
const auth = useAuthStore()
const { brandName, brandTagline, brandLogoUrl, loadBranding } = useBranding()

const mode = ref<'login' | 'register'>('login')
const oidcAvailable = ref(false)
const oidcLoading = ref(false)
const samlAvailable = ref(false)
const samlLoading = ref(false)

onMounted(async () => {
  // Load branding before auth (public endpoint)
  await loadBranding()
  // Check if OIDC/SSO is enabled (returns null if not)
  const [oidcUrl, samlUrl] = await Promise.all([
    authApi.getOidcLoginUrl(),
    authApi.getSamlLoginUrl(),
  ])
  oidcAvailable.value = oidcUrl !== null
  samlAvailable.value = samlUrl !== null
})

async function handleSsoLogin() {
  oidcLoading.value = true
  try {
    const url = await authApi.getOidcLoginUrl()
    if (url) {
      window.location.href = url
    } else {
      localError.value = 'SSO is not available'
    }
  } catch {
    localError.value = 'Failed to start SSO login'
  } finally {
    oidcLoading.value = false
  }
}

async function handleSamlLogin() {
  samlLoading.value = true
  try {
    const url = await authApi.getSamlLoginUrl()
    if (url) {
      window.location.href = url
    } else {
      localError.value = 'SAML SSO is not available'
    }
  } catch {
    localError.value = 'Failed to start SAML SSO login'
  } finally {
    samlLoading.value = false
  }
}
const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const localError = ref<string | null>(null)

// TOTP modal state
const showTotpModal = ref(false)
const totpMode = ref<'setup' | 'login'>('login')
const totpError = ref<string | null>(null)

async function handleSubmit() {
  localError.value = null

  if (!username.value.trim() || !password.value.trim()) {
    localError.value = 'Username and password are required'
    return
  }

  if (mode.value === 'register') {
    if (!email.value.trim()) {
      localError.value = 'Email is required'
      return
    }
    if (password.value !== confirmPassword.value) {
      localError.value = 'Passwords do not match'
      return
    }
    if (password.value.length < 8) {
      localError.value = 'Password must be at least 8 characters'
      return
    }
    if (!/[A-Z]/.test(password.value) || !/[a-z]/.test(password.value) || !/\d/.test(password.value)) {
      localError.value = 'Password must contain an uppercase letter, lowercase letter, and a digit'
      return
    }
    const ok = await auth.register(username.value.trim(), email.value.trim(), password.value)
    if (ok) {
      // Show QR code modal for TOTP setup
      totpMode.value = 'setup'
      totpError.value = null
      showTotpModal.value = true
    } else {
      localError.value = auth.error
    }
  } else {
    const result = await auth.login(username.value.trim(), password.value)
    if (result === 'ok') {
      const rawRedirect = (router.currentRoute.value.query.redirect as string) || '/dashboard'
      const redirect = rawRedirect.startsWith('/') && !rawRedirect.startsWith('//') ? rawRedirect : '/dashboard'
      router.push(redirect)
    } else if (result === 'totp') {
      // Show TOTP verification modal for login
      totpMode.value = 'login'
      totpError.value = null
      showTotpModal.value = true
    } else {
      localError.value = auth.error
    }
  }
}

async function handleTotpVerify(code: string) {
  totpError.value = null

  if (totpMode.value === 'setup') {
    const ok = await auth.verifyTotpSetup(code)
    if (ok) {
      showTotpModal.value = false
      router.push('/dashboard')
    } else {
      totpError.value = auth.error ?? 'Invalid code — please try again'
    }
  } else {
    const ok = await auth.loginWithTotp(code)
    if (ok) {
      showTotpModal.value = false
      const rawRedirect = (router.currentRoute.value.query.redirect as string) || '/dashboard'
      const redirect = rawRedirect.startsWith('/') && !rawRedirect.startsWith('//') ? rawRedirect : '/dashboard'
      router.push(redirect)
    } else {
      totpError.value = auth.error ?? 'Invalid code — please try again'
    }
  }
}

function handleTotpClose() {
  showTotpModal.value = false
  auth.pendingTotpLogin = null
}

function toggleMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  localError.value = null
  auth.error = null
}

</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4" style="background: var(--surface-alt);">
    <div class="w-full max-w-sm">

      <!-- Brand -->
      <div class="text-center mb-8">
        <div class="inline-flex items-center justify-center w-12 h-12 rounded-xl mb-4" style="background: rgba(var(--brand-primary-rgb), 0.1);">
          <img v-if="brandLogoUrl" :src="brandLogoUrl" alt="" class="w-6 h-6 object-contain" />
          <svg v-else class="w-6 h-6" style="color: var(--brand-primary);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <h1 class="text-xl font-bold tracking-tight" style="color: var(--heading);">{{ brandName }}</h1>
        <p class="text-sm mt-1" style="color: var(--text-3);">{{ brandTagline }}</p>
      </div>

      <!-- Card -->
      <div class="rounded-xl shadow-sm p-6" style="background: var(--surface); border: 1px solid var(--border);">
        <h2 class="text-base font-semibold mb-5" style="color: var(--heading);">
          {{ mode === 'login' ? 'Sign in' : 'Create account' }}
        </h2>

        <!-- Error -->
        <div
          v-if="localError"
          class="mb-4 px-3 py-2 text-sm rounded-lg"
          style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);"
          role="alert"
        >
          {{ localError }}
        </div>

        <form @submit.prevent="handleSubmit" class="space-y-4">
          <!-- Username -->
          <div>
            <label for="username" class="block text-xs font-medium mb-1" style="color: var(--text-2);">Username</label>
            <input
              id="username"
              v-model="username"
              type="text"
              autocomplete="username"
              required
              class="w-full px-3 py-2 text-sm rounded-lg outline-none transition"
              style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
              placeholder="Enter username"
            />
          </div>

          <!-- Email (register only) -->
          <div v-if="mode === 'register'">
            <label for="email" class="block text-xs font-medium mb-1" style="color: var(--text-2);">Email</label>
            <input
              id="email"
              v-model="email"
              type="email"
              autocomplete="email"
              required
              class="w-full px-3 py-2 text-sm rounded-lg outline-none transition"
              style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
              placeholder="you@company.com"
            />
          </div>

          <!-- Password -->
          <div>
            <label for="password" class="block text-xs font-medium mb-1" style="color: var(--text-2);">Password</label>
            <input
              id="password"
              v-model="password"
              type="password"
              autocomplete="current-password"
              required
              class="w-full px-3 py-2 text-sm rounded-lg outline-none transition"
              style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
              placeholder="Enter password"
            />
          </div>

          <!-- Confirm password (register only) -->
          <div v-if="mode === 'register'">
            <label for="confirm-password" class="block text-xs font-medium mb-1" style="color: var(--text-2);">Confirm Password</label>
            <input
              id="confirm-password"
              v-model="confirmPassword"
              type="password"
              autocomplete="new-password"
              required
              class="w-full px-3 py-2 text-sm rounded-lg outline-none transition"
              style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
              placeholder="Confirm password"
            />
          </div>

          <!-- Submit -->
          <button
            type="submit"
            :disabled="auth.isLoading"
            class="w-full py-2 px-4 text-sm font-medium text-white bg-[var(--brand-primary)] hover:bg-[var(--brand-primary-dark)] rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span v-if="auth.isLoading" class="inline-flex items-center gap-2">
              <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              {{ mode === 'login' ? 'Signing in…' : 'Creating account…' }}
            </span>
            <span v-else>{{ mode === 'login' ? 'Sign in' : 'Create account' }}</span>
          </button>
        </form>

        <!-- SSO / OIDC / SAML -->
        <div v-if="(oidcAvailable || samlAvailable) && mode === 'login'" class="mt-4">
          <div class="relative flex items-center justify-center my-3">
            <div class="absolute inset-0 flex items-center"><div class="w-full" style="border-top: 1px solid var(--border-light);"></div></div>
            <span class="relative px-3 text-[11px] uppercase tracking-wider" style="background: var(--surface); color: var(--text-3);">or</span>
          </div>
          <div class="space-y-2">
            <button
              v-if="oidcAvailable"
              type="button"
              :disabled="oidcLoading"
              class="w-full py-2 px-4 text-sm font-medium rounded-lg transition flex items-center justify-center gap-2 disabled:opacity-50"
              style="color: var(--text-2); background: var(--surface); border: 1px solid var(--border);"
              @click="handleSsoLogin"
            >
              <svg class="w-4 h-4" style="color: var(--text-3);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 11c0 3.517-1.009 6.799-2.753 9.571m-3.44-2.04l.054-.09A13.916 13.916 0 008 11a4 4 0 118 0c0 1.017-.07 2.019-.203 3m-2.118 6.844A21.88 21.88 0 0015.171 17m3.839 1.132c.645-2.266.99-4.659.99-7.132A8 8 0 008 4.07M3 15.364c.64-1.319 1-2.8 1-4.364 0-1.457.39-2.823 1.07-4" />
              </svg>
              {{ oidcLoading ? 'Redirecting…' : 'Sign in with SSO' }}
            </button>
            <button
              v-if="samlAvailable"
              type="button"
              :disabled="samlLoading"
              class="w-full py-2 px-4 text-sm font-medium rounded-lg transition flex items-center justify-center gap-2 disabled:opacity-50"
              style="color: var(--text-2); background: var(--surface); border: 1px solid var(--border);"
              @click="handleSamlLogin"
            >
              <svg class="w-4 h-4" style="color: var(--text-3);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
              {{ samlLoading ? 'Redirecting…' : 'Sign in with SAML SSO' }}
            </button>
          </div>
        </div>

        <!-- Toggle -->
        <div class="mt-5 pt-4 text-center" style="border-top: 1px solid var(--border-light);">
          <button
            @click="toggleMode"
            class="text-sm text-[var(--brand-primary)] hover:text-[var(--brand-primary-dark)] font-medium transition"
          >
            {{ mode === 'login' ? "Don't have an account? Register" : 'Already have an account? Sign in' }}
          </button>
        </div>
      </div>

    </div>
  </div>

  <!-- TOTP Modal -->
  <TotpModal
    v-if="showTotpModal"
    :mode="totpMode"
    :qr-code-svg="auth.pendingTotpSetup?.qr_code_svg"
    :loading="auth.isLoading"
    :error="totpError"
    @verify="handleTotpVerify"
    @close="handleTotpClose"
  />
</template>
