/**
 * Axios HTTP client configured for the Sentora backend API.
 *
 * Base URL resolves to /api/v1 in production (same origin, served by FastAPI).
 * In development the Vite proxy is used so the dev server forwards /api calls
 * to the FastAPI backend on port 5002.
 *
 * Auth: a request interceptor reads the JWT from localStorage and attaches it
 * as a Bearer token. A response interceptor transparently refreshes the access
 * token using the stored refresh token on 401 responses, then retries the
 * original request. If refresh fails, the user is redirected to /login.
 *
 * CSP note: the backend's Content-Security-Policy uses 'unsafe-inline' for
 * style-src because Vue 3 and Tailwind CSS inject inline styles at runtime.
 * This is a known trade-off — nonce-based CSP for inline styles is not yet
 * practical with the current Vue/Vite toolchain.
 */

import axios, { type AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'

/** Standardised error shape returned by the backend for all failures. */
export interface ApiError {
  error_code: string
  message: string
  detail: Record<string, unknown>
}

const TOKEN_KEY = 'sentora_token'
const REFRESH_KEY = 'sentora_refresh_token'
const TENANT_KEY = 'sentora_tenant'

const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
})

/** Request interceptor — attach JWT Bearer token and tenant ID if available. */
client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  const tenant = localStorage.getItem(TENANT_KEY)
  if (tenant && config.headers) {
    config.headers['X-Tenant-ID'] = tenant
  }
  return config
})

// ── Transparent token refresh on 401 ────────────────────────────────────────

/**
 * Promise-based mutex for token refresh.  All concurrent 401 handlers
 * await the same refresh promise, ensuring only one refresh call is in
 * flight at a time and all queued requests get the new token.
 */
let refreshPromise: Promise<string> | null = null

function clearAuthAndRedirect() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
  if (!window.location.pathname.startsWith('/login')) {
    import('@/router').then(({ default: router }) => {
      router.push({ path: '/login', query: { redirect: router.currentRoute.value.fullPath } })
    }).catch(() => {
      window.location.href = '/login'
    })
  }
}

/**
 * Execute the actual token refresh call.  Returns the new access token
 * on success.  On failure clears auth state and redirects to login.
 */
async function doRefresh(): Promise<string> {
  const refreshToken = localStorage.getItem(REFRESH_KEY)
  if (!refreshToken) {
    clearAuthAndRedirect()
    throw new Error('No refresh token available')
  }
  const resp = await axios.post<{ access_token: string; refresh_token: string }>(
    '/api/v1/auth/refresh',
    { refresh_token: refreshToken },
    { headers: { 'Content-Type': 'application/json' }, timeout: 10_000 },
  )
  localStorage.setItem(TOKEN_KEY, resp.data.access_token)
  localStorage.setItem(REFRESH_KEY, resp.data.refresh_token)
  return resp.data.access_token
}

/** Response interceptor — attempt transparent refresh on 401. */
client.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // Only attempt refresh on 401, and not for auth endpoints themselves
    if (
      error.response?.status !== 401 ||
      originalRequest._retry ||
      originalRequest.url?.startsWith('/auth/login') ||
      originalRequest.url?.startsWith('/auth/refresh') ||
      originalRequest.url?.startsWith('/auth/register')
    ) {
      // For non-refreshable 401s, clear auth and redirect
      if (error.response?.status === 401 && !originalRequest.url?.startsWith('/auth/')) {
        clearAuthAndRedirect()
      }
      const apiErr = error.response?.data
      if (apiErr?.error_code) {
        return Promise.reject(new Error(`[${apiErr.error_code}] ${apiErr.message}`))
      }
      return Promise.reject(error)
    }

    originalRequest._retry = true

    try {
      // All concurrent 401s share a single refresh promise
      if (!refreshPromise) {
        refreshPromise = doRefresh().finally(() => {
          refreshPromise = null
        })
      }
      const newAccessToken = await refreshPromise

      // Retry the original request with the new token
      originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
      return client(originalRequest)
    } catch (refreshError) {
      clearAuthAndRedirect()
      return Promise.reject(refreshError)
    }
  },
)

export default client
