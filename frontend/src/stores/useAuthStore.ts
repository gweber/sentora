/**
 * Auth store — manages JWT access/refresh tokens, user info, login/logout, TOTP 2FA.
 *
 * Access token (short-lived, 15 min) is stored in localStorage for API calls.
 * Refresh token (long-lived, 7 days) is stored in localStorage and used by the
 * axios interceptor to transparently obtain new access tokens on 401.
 *
 * On init, if tokens exist, validates by calling GET /auth/me.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authApi from '@/api/auth'
import type { UserInfo, TotpSetupResponse } from '@/types/auth'
import { useBranding } from '@/composables/useBranding'
import { useDeployment } from '@/composables/useDeployment'

const TOKEN_KEY = 'sentora_token'
const REFRESH_KEY = 'sentora_refresh_token'
export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const refreshToken = ref<string | null>(localStorage.getItem(REFRESH_KEY))
  const user = ref<UserInfo | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const initialized = ref(false)

  // TOTP state for registration flow
  const pendingTotpSetup = ref<TotpSetupResponse | null>(null)
  const pendingTotpSetupPassword = ref<string | null>(null)
  // TOTP state for login flow
  const pendingTotpLogin = ref<{ username: string; password: string } | null>(null)

  // Timer IDs for password expiration timeouts (cleared on logout)
  let _totpLoginTimer: ReturnType<typeof setTimeout> | null = null
  let _totpSetupTimer: ReturnType<typeof setTimeout> | null = null

  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const role = computed(() => user.value?.role ?? null)
  const isSuperAdmin = computed(() => user.value?.role === 'super_admin')
  const isAdmin = computed(() => user.value?.role === 'admin' || user.value?.role === 'super_admin')
  const isAnalyst = computed(() => user.value?.role === 'analyst' || user.value?.role === 'admin' || user.value?.role === 'super_admin')

  function setTokens(access: string | null, refresh: string | null = null) {
    token.value = access
    refreshToken.value = refresh
    if (access) {
      localStorage.setItem(TOKEN_KEY, access)
    } else {
      localStorage.removeItem(TOKEN_KEY)
    }
    if (refresh) {
      localStorage.setItem(REFRESH_KEY, refresh)
    } else {
      localStorage.removeItem(REFRESH_KEY)
    }
  }

  /**
   * Login step 1: username + password.
   * Returns 'ok' if logged in, 'totp' if 2FA code needed, 'error' on failure.
   */
  async function login(username: string, password: string): Promise<'ok' | 'totp' | 'error'> {
    isLoading.value = true
    error.value = null
    try {
      const resp = await authApi.login({ username, password })
      setTokens(resp.access_token, resp.refresh_token)
      await fetchUser()
      return 'ok'
    } catch (err: unknown) {
      // Check if the 401 response signals TOTP is required
      const axiosErr = err as { response?: { status?: number; data?: { detail?: { requires_totp?: boolean } } } }
      if (
        axiosErr?.response?.status === 401 &&
        axiosErr?.response?.data?.detail?.requires_totp
      ) {
        pendingTotpLogin.value = { username, password }
        // Clear cached password after 5 minutes to limit exposure window
        if (_totpLoginTimer) clearTimeout(_totpLoginTimer)
        _totpLoginTimer = setTimeout(() => { pendingTotpLogin.value = null }, 5 * 60 * 1000)
        return 'totp'
      }
      error.value = err instanceof Error ? err.message : 'Login failed'
      setTokens(null)
      user.value = null
      return 'error'
    } finally {
      isLoading.value = false
    }
  }

  /** Login step 2: verify TOTP code for login. */
  async function loginWithTotp(code: string): Promise<boolean> {
    if (!pendingTotpLogin.value) return false
    isLoading.value = true
    error.value = null
    try {
      const { username, password } = pendingTotpLogin.value
      pendingTotpLogin.value = null
      const resp = await authApi.login({ username, password, totp_code: code })
      if (resp.requires_totp) {
        error.value = 'Invalid TOTP code'
        return false
      }
      setTokens(resp.access_token, resp.refresh_token)
      await fetchUser()
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Invalid code'
      return false
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Register: creates account, returns TOTP setup data (QR code).
   * Does NOT log in yet — must call verifyTotpSetup first.
   */
  async function register(username: string, email: string, password: string): Promise<boolean> {
    isLoading.value = true
    error.value = null
    try {
      const setup = await authApi.register({ username, email, password })
      pendingTotpSetup.value = setup
      pendingTotpSetupPassword.value = password
      // Clear cached password after 5 minutes to limit exposure window
      if (_totpSetupTimer) clearTimeout(_totpSetupTimer)
      _totpSetupTimer = setTimeout(() => { pendingTotpSetupPassword.value = null }, 5 * 60 * 1000)
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Registration failed'
      return false
    } finally {
      isLoading.value = false
    }
  }

  /** Verify first TOTP code after registration to activate 2FA + get tokens. */
  async function verifyTotpSetup(code: string): Promise<boolean> {
    if (!pendingTotpSetup.value || !pendingTotpSetupPassword.value) return false
    isLoading.value = true
    error.value = null
    try {
      const resp = await authApi.verifyTotpSetup({
        username: pendingTotpSetup.value.user.username,
        password: pendingTotpSetupPassword.value,
        code,
      })
      setTokens(resp.access_token, resp.refresh_token)
      await fetchUser()
      pendingTotpSetup.value = null
      pendingTotpSetupPassword.value = null
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Invalid code'
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function fetchUser(): Promise<void> {
    if (!token.value) return
    try {
      user.value = await authApi.getMe()
    } catch {
      setTokens(null)
      user.value = null
    }
  }

  /** Called once on app startup to validate a stored token. */
  let _initPromise: Promise<void> | null = null
  async function init(): Promise<void> {
    if (initialized.value) return
    // Deduplicate concurrent init() calls (e.g. multiple route guards firing)
    if (_initPromise) return _initPromise
    _initPromise = (async () => {
      if (token.value) {
        await fetchUser()
      }
      initialized.value = true
    })()
    try {
      await _initPromise
    } finally {
      _initPromise = null
    }
  }

  /** Clear all auth state, timers, and dependent composables. */
  function _clearAuthState(): void {
    setTokens(null)
    user.value = null
    initialized.value = false
    pendingTotpSetup.value = null
    pendingTotpSetupPassword.value = null
    pendingTotpLogin.value = null
    if (_totpLoginTimer) { clearTimeout(_totpLoginTimer); _totpLoginTimer = null }
    if (_totpSetupTimer) { clearTimeout(_totpSetupTimer); _totpSetupTimer = null }
    useBranding().reset()
    useDeployment().reset()
  }

  async function logout() {
    // Revoke refresh token on the server (best-effort)
    if (refreshToken.value) {
      try {
        await authApi.logout(refreshToken.value)
      } catch {
        // Server-side revocation is best-effort; clear locally regardless
      }
    }
    _clearAuthState()
  }

  /** Logout from all devices — revokes all refresh tokens server-side. */
  async function logoutAll() {
    try {
      await authApi.logoutAll()
    } catch {
      // Best-effort
    }
    _clearAuthState()
  }

  /** Complete OIDC login by exchanging callback params for tokens. */
  async function loginWithOidc(code: string, state: string): Promise<boolean> {
    isLoading.value = true
    error.value = null
    try {
      const resp = await authApi.oidcCallback(code, state)
      setTokens(resp.access_token, resp.refresh_token)
      await fetchUser()
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'SSO login failed'
      setTokens(null)
      user.value = null
      return false
    } finally {
      isLoading.value = false
    }
  }

  /** Complete SAML login by exchanging a one-time nonce for JWT tokens. */
  async function loginWithSamlNonce(nonce: string): Promise<boolean> {
    isLoading.value = true
    error.value = null
    try {
      const resp = await authApi.samlExchange(nonce)
      setTokens(resp.access_token, resp.refresh_token)
      await fetchUser()
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'SAML login failed'
      setTokens(null)
      user.value = null
      return false
    } finally {
      isLoading.value = false
    }
  }

  /** Change the current user's password. */
  async function changePassword(currentPw: string, newPw: string): Promise<boolean> {
    isLoading.value = true
    error.value = null
    try {
      await authApi.changePassword({ current_password: currentPw, new_password: newPw })
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Password change failed'
      return false
    } finally {
      isLoading.value = false
    }
  }

  return {
    token,
    refreshToken,
    user,
    isLoading,
    error,
    initialized,
    pendingTotpSetup,
    pendingTotpLogin,
    isAuthenticated,
    role,
    isSuperAdmin,
    isAdmin,
    isAnalyst,
    login,
    loginWithTotp,
    loginWithOidc,
    loginWithSamlNonce,
    register,
    verifyTotpSetup,
    fetchUser,
    init,
    logout,
    logoutAll,
    changePassword,
  }
})
