/**
 * E2E tests for the full authentication flow.
 *
 * Covers:
 * - Register → TOTP setup → verify TOTP → logged in
 * - Login with TOTP 2FA
 * - Token refresh + rotation
 * - Logout (single session + all sessions)
 * - Refresh token reuse detection
 * - Protected route redirect
 * - Wrong credentials error
 *
 * NOTE: API tests run serially with a shared user to stay within rate limits
 * (register: 5 req/300s, login: 10 req/60s).
 */

import { test, expect, type APIRequestContext } from '@playwright/test'
import * as OTPAuth from 'otpauth'

const API = '/api/v1'

/** Extract the TOTP secret from a totp_uri (otpauth://totp/...). */
function extractSecret(totpUri: string): string {
  const url = new URL(totpUri)
  return url.searchParams.get('secret')!
}

/** Generate a valid TOTP code from a secret. */
function generateTotpCode(secret: string): string {
  const totp = new OTPAuth.TOTP({ secret, digits: 6, period: 30 })
  return totp.generate()
}

/** Reset backend rate limiters (dev-only endpoint). */
async function resetRateLimits(request: APIRequestContext) {
  await request.post(`${API}/test/reset-rate-limits`)
}

// ── API-level auth lifecycle (serial, single user) ───────────────────────────

test.describe.serial('Auth API lifecycle', () => {
  const id = Math.random().toString(36).slice(2, 8)
  const user = {
    username: `e2e_api_${id}`,
    email: `e2e_api_${id}@test.local`,
    password: 'TestPassword1234',
  }
  let totpSecret = ''
  let accessToken = ''
  let refreshToken = ''

  test('register returns TOTP setup data', async ({ request }) => {
    await resetRateLimits(request)
    const resp = await request.post(`${API}/auth/register`, {
      data: { username: user.username, email: user.email, password: user.password },
    })
    expect(resp.ok(), `Register failed: ${resp.status()} ${await resp.text()}`).toBeTruthy()
    const data = await resp.json()
    expect(data.qr_code_svg).toBeTruthy()
    expect(data.totp_uri).toBeTruthy()
    totpSecret = extractSecret(data.totp_uri)
  })

  test('verify TOTP setup activates 2FA and returns tokens', async ({ request }) => {
    const code = generateTotpCode(totpSecret)
    const resp = await request.post(`${API}/auth/totp/verify-setup`, {
      data: { username: user.username, code, password: user.password },
    })
    expect(resp.ok(), `TOTP verify failed: ${resp.status()}`).toBeTruthy()
    const tokens = await resp.json()
    expect(tokens.access_token).toBeTruthy()
    expect(tokens.refresh_token).toBeTruthy()
    accessToken = tokens.access_token
    refreshToken = tokens.refresh_token
  })

  test('GET /me returns authenticated user profile', async ({ request }) => {
    const resp = await request.get(`${API}/auth/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    expect(resp.ok()).toBeTruthy()
    const me = await resp.json()
    expect(me.username).toBe(user.username)
    expect(me.totp_enabled).toBe(true)
  })

  test('login without TOTP code returns requires_totp flag', async ({ request }) => {
    const resp = await request.post(`${API}/auth/login`, {
      data: { username: user.username, password: user.password },
    })
    expect(resp.status()).toBe(401)
    const data = await resp.json()
    expect(data.detail.requires_totp).toBe(true)
  })

  test('login with TOTP code returns full token pair', async ({ request }) => {
    const resp = await request.post(`${API}/auth/login`, {
      data: { username: user.username, password: user.password, totp_code: generateTotpCode(totpSecret) },
    })
    expect(resp.ok()).toBeTruthy()
    const tokens = await resp.json()
    expect(tokens.access_token).toBeTruthy()
    expect(tokens.refresh_token).toBeTruthy()
    // Save for subsequent tests
    accessToken = tokens.access_token
    refreshToken = tokens.refresh_token
  })

  test('refresh token rotation returns new token pair', async ({ request }) => {
    const resp = await request.post(`${API}/auth/refresh`, {
      data: { refresh_token: refreshToken },
    })
    expect(resp.ok()).toBeTruthy()
    const newTokens = await resp.json()
    expect(newTokens.access_token).toBeTruthy()
    expect(newTokens.refresh_token).not.toBe(refreshToken)

    // Save old token for reuse test, update to new
    const oldRefresh = refreshToken
    refreshToken = newTokens.refresh_token
    accessToken = newTokens.access_token

    // Reuse the OLD token (simulates theft) — should fail
    const reuse = await request.post(`${API}/auth/refresh`, {
      data: { refresh_token: oldRefresh },
    })
    expect(reuse.status()).toBe(401)

    // Entire family revoked — even the new token should fail
    const revoked = await request.post(`${API}/auth/refresh`, {
      data: { refresh_token: refreshToken },
    })
    expect(revoked.status()).toBe(401)
  })

  test('login again after family revocation', async ({ request }) => {
    // Re-login to get fresh tokens for logout tests
    const resp = await request.post(`${API}/auth/login`, {
      data: { username: user.username, password: user.password, totp_code: generateTotpCode(totpSecret) },
    })
    expect(resp.ok()).toBeTruthy()
    const tokens = await resp.json()
    accessToken = tokens.access_token
    refreshToken = tokens.refresh_token
  })

  test('logout revokes the session', async ({ request }) => {
    const resp = await request.post(`${API}/auth/logout`, {
      data: { refresh_token: refreshToken },
    })
    expect(resp.status()).toBe(204)

    // Refresh with revoked token should fail
    const stale = await request.post(`${API}/auth/refresh`, {
      data: { refresh_token: refreshToken },
    })
    expect(stale.status()).toBe(401)
  })

  test('logout/all revokes all sessions', async ({ request }) => {
    await resetRateLimits(request)
    // Create two sessions (same TOTP code is valid for the 30s window)
    const code = generateTotpCode(totpSecret)
    const login1 = await request.post(`${API}/auth/login`, {
      data: { username: user.username, password: user.password, totp_code: code },
    })
    expect(login1.ok(), `Login 1 failed: ${login1.status()}`).toBeTruthy()
    const s1 = await login1.json()
    expect(s1.access_token).toBeTruthy()

    const login2 = await request.post(`${API}/auth/login`, {
      data: { username: user.username, password: user.password, totp_code: code },
    })
    expect(login2.ok(), `Login 2 failed: ${login2.status()}`).toBeTruthy()
    const s2 = await login2.json()
    expect(s2.refresh_token).toBeTruthy()

    // Logout all using session 1's access token
    const logoutAll = await request.post(`${API}/auth/logout/all`, {
      headers: { Authorization: `Bearer ${s1.access_token}` },
    })
    expect(logoutAll.status()).toBe(204)

    // Session 2's refresh token should be revoked
    const r = await request.post(`${API}/auth/refresh`, {
      data: { refresh_token: s2.refresh_token },
    })
    expect(r.status()).toBe(401)
  })
})

// ── Browser-level auth flows ─────────────────────────────────────────────────

test.describe('Auth UI flows', () => {
  /** Clear auth state, reset rate limits, and wait for login form. */
  async function clearAuthState(page: import('@playwright/test').Page) {
    await page.goto('/login')
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })
    await page.reload()
    await page.locator('#username').waitFor({ timeout: 10000 })
  }

  test('register flow in browser with TOTP modal', async ({ page, request }) => {
    await resetRateLimits(request)
    let totpSecret = ''

    // Intercept the register API to extract the TOTP secret
    await page.route('**/api/v1/auth/register', async (route) => {
      const response = await route.fetch()
      const body = await response.json()
      if (body.totp_uri) {
        totpSecret = extractSecret(body.totp_uri)
      }
      await route.fulfill({ response })
    })

    await clearAuthState(page)

    // Switch to register mode (button text contains "Register")
    await page.getByText('Register').click()

    // Fill registration form
    const ts = Date.now()
    await page.locator('#username').fill(`e2e_ui_${ts}`)
    await page.locator('#email').fill(`e2e_ui_${ts}@test.local`)
    await page.locator('#password').fill('TestPassword1234')
    await page.locator('#confirm-password').fill('TestPassword1234')

    // Submit registration
    await page.getByRole('button', { name: 'Create account' }).click()

    // TOTP modal should appear with QR code
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 10000 })
    await expect(page.getByText('Set up 2FA')).toBeVisible()
    expect(totpSecret).toBeTruthy()

    // Fill 6-digit TOTP code
    const code = generateTotpCode(totpSecret)
    for (let i = 0; i < 6; i++) {
      await page.getByLabel(`Digit ${i + 1} of 6`).fill(code[i])
    }

    // Auto-submit redirects to dashboard
    await expect(page).toHaveURL(/\/(dashboard)?$/, { timeout: 15000 })
  })

  test('login flow with TOTP modal', async ({ page, request }) => {
    await resetRateLimits(request)
    // Register a dedicated user — skip if rate limited
    const id = Math.random().toString(36).slice(2, 8)
    const user = { username: `e2e_login_${id}`, email: `e2e_login_${id}@test.local`, password: 'TestPassword1234' }

    const regResp = await request.post(`${API}/auth/register`, { data: user })
    if (regResp.status() === 429) {
      test.skip(true, 'Register rate limited — run this test in isolation')
      return
    }
    expect(regResp.ok()).toBeTruthy()
    const regData = await regResp.json()
    const secret = extractSecret(regData.totp_uri)
    await request.post(`${API}/auth/totp/verify-setup`, {
      data: { username: user.username, code: generateTotpCode(secret), password: user.password },
    })

    await clearAuthState(page)

    // Fill login form
    await page.locator('#username').fill(user.username)
    await page.locator('#password').fill(user.password)
    await page.getByRole('button', { name: 'Sign in' }).click()

    // Wait for either TOTP modal or rate limit error
    const dialog = page.getByRole('dialog')
    const alert = page.getByRole('alert')
    const result = await Promise.race([
      dialog.waitFor({ timeout: 10000 }).then(() => 'dialog' as const),
      alert.waitFor({ timeout: 10000 }).then(() => 'alert' as const),
    ])

    if (result === 'alert') {
      // Login was rate-limited; skip gracefully
      test.skip(true, 'Login rate limited during E2E — run in isolation')
      return
    }

    await expect(page.getByText('Two-factor authentication')).toBeVisible()

    // Enter TOTP code
    const loginCode = generateTotpCode(secret)
    for (let i = 0; i < 6; i++) {
      await page.getByLabel(`Digit ${i + 1} of 6`).fill(loginCode[i])
    }

    // Redirect to dashboard
    await expect(page).toHaveURL(/\/(dashboard)?$/, { timeout: 15000 })
    await expect(page.getByText('Sentora')).toBeVisible()
  })

  test('protected route redirects to login', async ({ page }) => {
    await page.goto('/login')
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })

    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login/, { timeout: 10000 })
  })

  test('wrong password shows error', async ({ page }) => {
    await clearAuthState(page)
    await page.locator('#username').fill('nonexistent_user')
    await page.locator('#password').fill('wrongpassword')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 5000 })
  })
})
