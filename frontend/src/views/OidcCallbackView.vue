<!--
  SSO callback handler — handles both:
  1. OIDC: receives code+state, exchanges for tokens via backend
  2. SAML: receives a one-time nonce, exchanges for tokens via POST /auth/saml/exchange
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/useAuthStore'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const error = ref<string | null>(null)

onMounted(async () => {
  const oidcError = route.query.error as string | undefined
  const errorDesc = route.query.error_description as string | undefined

  if (oidcError) {
    error.value = errorDesc || oidcError
    return
  }

  // SAML flow: backend redirects with a one-time nonce (tokens stored server-side)
  const samlNonce = route.query.saml_nonce as string | undefined
  if (samlNonce) {
    const ok = await auth.loginWithSamlNonce(samlNonce)
    if (ok) {
      router.replace('/dashboard')
    } else {
      error.value = auth.error ?? 'SAML authentication failed'
    }
    return
  }

  // OIDC flow: backend redirects with code + state for exchange
  const code = route.query.code as string | undefined
  const state = route.query.state as string | undefined

  if (!code || !state) {
    error.value = 'Missing authorization code or state parameter'
    return
  }

  const ok = await auth.loginWithOidc(code, state)
  if (ok) {
    router.replace('/dashboard')
  } else {
    error.value = auth.error ?? 'SSO authentication failed'
  }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4" style="background: var(--surface-alt);">
    <div class="w-full max-w-sm text-center">

      <!-- Loading state -->
      <div v-if="!error" class="space-y-4">
        <svg class="w-8 h-8 animate-spin text-[var(--brand-primary)] mx-auto" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <p class="text-[14px]" style="color: var(--text-2);">Completing SSO sign-in…</p>
      </div>

      <!-- Error state -->
      <div v-else class="space-y-4">
        <div class="w-12 h-12 rounded-full bg-[var(--error-bg)] flex items-center justify-center mx-auto">
          <svg class="w-6 h-6 text-[var(--error-text)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <div>
          <p class="text-[15px] font-semibold mb-1" style="color: var(--heading);">SSO Login Failed</p>
          <p class="text-[13px]" style="color: var(--text-3);">{{ error }}</p>
        </div>
        <router-link
          to="/login"
          class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--brand-primary)] text-white text-[13px] font-medium hover:bg-[var(--brand-primary-dark)] transition-colors no-underline"
        >
          Back to sign in
        </router-link>
      </div>

    </div>
  </div>
</template>
