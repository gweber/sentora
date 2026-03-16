/**
 * E2E test helpers for Sentora.
 *
 * Since the app requires TOTP for full authentication, most E2E tests
 * operate on public pages (login) or use API-level assertions.
 */

import { type Page, type APIRequestContext } from '@playwright/test'

/**
 * Navigate to the login page and wait for it to render.
 */
export async function goToLogin(page: Page) {
  await page.goto('/login')
  await page.waitForSelector('h2:has-text("Sign in")')
}

/**
 * Fill the login form fields without submitting.
 */
export async function fillLoginForm(page: Page, username: string, password: string) {
  await page.fill('#username', username)
  await page.fill('#password', password)
}

/**
 * Reset backend rate limits (dev-only endpoint).
 * Call this before tests that hit auth endpoints repeatedly.
 */
export async function resetRateLimits(request: APIRequestContext) {
  try {
    await request.post('/api/v1/test/reset-rate-limits')
  } catch {
    // Endpoint may not exist in production builds — ignore
  }
}

/**
 * Register a user via the API. Returns the response body.
 * Note: The user will still need TOTP setup to fully authenticate.
 */
export async function registerUserViaApi(
  request: APIRequestContext,
  username: string,
  email: string,
  password: string,
) {
  const response = await request.post('/api/v1/auth/register', {
    data: { username, email, password },
  })
  return { status: response.status(), body: await response.json().catch(() => null) }
}
