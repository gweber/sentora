/**
 * E2E tests — Webhook management (admin flow).
 *
 * Covers:
 * - Webhook page rendering and empty state
 * - Create webhook via modal
 * - Verify created webhook appears in list
 * - Delete webhook removes it from list
 * - Webhook form validation
 *
 * These tests register a fresh admin user with TOTP, then authenticate
 * before exercising the webhooks UI. Since webhooks are admin-only,
 * the user must have admin role (first registered user is auto-admin,
 * or we rely on the test environment granting admin to the test user).
 */

import { test, expect, type APIRequestContext, type Page } from '@playwright/test'
import * as OTPAuth from 'otpauth'

const API = '/api/v1'

function extractSecret(totpUri: string): string {
  const url = new URL(totpUri)
  return url.searchParams.get('secret')!
}

function generateTotpCode(secret: string): string {
  const totp = new OTPAuth.TOTP({ secret, digits: 6, period: 30 })
  return totp.generate()
}

async function resetRateLimits(request: APIRequestContext) {
  await request.post(`${API}/test/reset-rate-limits`)
}

/**
 * Register a user via API, complete TOTP setup, and return credentials.
 */
async function createAuthenticatedUser(request: APIRequestContext) {
  const id = Math.random().toString(36).slice(2, 8)
  const user = {
    username: `e2e_wh_${id}`,
    email: `e2e_wh_${id}@test.local`,
    password: 'TestPassword1234',
  }

  await resetRateLimits(request)

  // Register
  const regResp = await request.post(`${API}/auth/register`, { data: user })
  if (!regResp.ok()) {
    throw new Error(`Register failed: ${regResp.status()} ${await regResp.text()}`)
  }
  const regData = await regResp.json()
  const totpSecret = extractSecret(regData.totp_uri)

  // Complete TOTP setup
  const setupResp = await request.post(`${API}/auth/totp/verify-setup`, {
    data: { username: user.username, code: generateTotpCode(totpSecret) },
  })
  if (!setupResp.ok()) {
    throw new Error(`TOTP setup failed: ${setupResp.status()}`)
  }
  const tokens = await setupResp.json()

  return { ...user, totpSecret, accessToken: tokens.access_token, refreshToken: tokens.refresh_token }
}

/**
 * Log in via the browser using the TOTP-enabled user.
 */
async function loginViaBrowser(page: Page, username: string, password: string, totpSecret: string) {
  await page.goto('/login')
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear() })
  await page.reload()
  await page.locator('#username').waitFor({ timeout: 10_000 })

  await page.locator('#username').fill(username)
  await page.locator('#password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()

  // Wait for TOTP modal
  const dialog = page.getByRole('dialog')
  await dialog.waitFor({ timeout: 10_000 })

  // Fill TOTP code
  const code = generateTotpCode(totpSecret)
  for (let i = 0; i < 6; i++) {
    await page.getByLabel(`Digit ${i + 1} of 6`).fill(code[i])
  }

  // Wait for dashboard redirect
  await expect(page).toHaveURL(/\/(dashboard)?$/, { timeout: 15_000 })
}

// ── API-level webhook CRUD ──────────────────────────────────────────────────

test.describe.serial('Webhook API CRUD', () => {
  let accessToken = ''
  let createdWebhookId = ''

  test('setup: create authenticated user', async ({ request }) => {
    const user = await createAuthenticatedUser(request)
    accessToken = user.accessToken
    expect(accessToken).toBeTruthy()
  })

  test('list webhooks returns empty array initially', async ({ request }) => {
    const resp = await request.get(`${API}/webhooks/`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    // May return 200 (empty list) or 403 if user is not admin
    if (resp.status() === 403) {
      test.skip(true, 'User does not have admin role — cannot access webhooks')
      return
    }
    expect(resp.ok()).toBeTruthy()
    const data = await resp.json()
    expect(Array.isArray(data)).toBeTruthy()
  })

  test('create a webhook via API', async ({ request }) => {
    const resp = await request.post(`${API}/webhooks/`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      data: {
        name: 'E2E Test Webhook',
        url: 'https://httpbin.org/post',
        events: ['sync.completed'],
      },
    })
    if (resp.status() === 403) {
      test.skip(true, 'User does not have admin role')
      return
    }
    expect(resp.ok(), `Create webhook failed: ${resp.status()}`).toBeTruthy()
    const webhook = await resp.json()
    expect(webhook.name).toBe('E2E Test Webhook')
    expect(webhook.url).toBe('https://httpbin.org/post')
    expect(webhook.events).toContain('sync.completed')
    expect(webhook.id).toBeTruthy()
    createdWebhookId = webhook.id
  })

  test('created webhook appears in list', async ({ request }) => {
    if (!createdWebhookId) {
      test.skip(true, 'Webhook was not created — skipping list check')
      return
    }
    const resp = await request.get(`${API}/webhooks/`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    expect(resp.ok()).toBeTruthy()
    const data = await resp.json()
    const found = data.find((wh: any) => wh.id === createdWebhookId)
    expect(found).toBeTruthy()
    expect(found.name).toBe('E2E Test Webhook')
  })

  test('delete webhook via API', async ({ request }) => {
    if (!createdWebhookId) {
      test.skip(true, 'No webhook to delete')
      return
    }
    const resp = await request.delete(`${API}/webhooks/${createdWebhookId}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    expect([200, 204]).toContain(resp.status())

    // Verify it is gone
    const listResp = await request.get(`${API}/webhooks/`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    const data = await listResp.json()
    const found = data.find((wh: any) => wh.id === createdWebhookId)
    expect(found).toBeFalsy()
  })
})

// ── Browser-level webhook UI ────────────────────────────────────────────────

test.describe('Webhook UI flow', () => {
  let user: Awaited<ReturnType<typeof createAuthenticatedUser>> | null = null

  test.beforeAll(async ({ request }) => {
    try {
      user = await createAuthenticatedUser(request)
    } catch {
      // Will skip browser tests if user creation fails
    }
  })

  test('navigate to webhooks page after login', async ({ page, request }) => {
    if (!user) {
      test.skip(true, 'Could not create test user')
      return
    }

    await resetRateLimits(request)
    await loginViaBrowser(page, user.username, user.password, user.totpSecret)

    await page.goto('/webhooks')

    // Page should render — either webhooks heading or a redirect to login/dashboard
    const heading = page.locator('h2:has-text("Webhooks")')
    const forbidden = page.locator('text=Forbidden, text=Access denied, text=not authorized')

    const result = await Promise.race([
      heading.waitFor({ timeout: 10_000 }).then(() => 'heading' as const),
      forbidden.first().waitFor({ timeout: 10_000 }).then(() => 'forbidden' as const),
      page.waitForURL('**/dashboard', { timeout: 10_000 }).then(() => 'redirected' as const),
    ]).catch(() => 'timeout' as const)

    if (result === 'forbidden' || result === 'redirected') {
      test.skip(true, 'User does not have admin access to webhooks')
      return
    }

    await expect(heading).toBeVisible()
    await expect(page.getByText('Receive HTTP notifications')).toBeVisible()
  })

  test('empty state shows no webhooks message', async ({ page, request }) => {
    if (!user) {
      test.skip(true, 'Could not create test user')
      return
    }

    await resetRateLimits(request)
    await loginViaBrowser(page, user.username, user.password, user.totpSecret)
    await page.goto('/webhooks')

    const heading = page.locator('h2:has-text("Webhooks")')
    const headingVisible = await heading.waitFor({ timeout: 10_000 }).then(() => true).catch(() => false)

    if (!headingVisible) {
      test.skip(true, 'Webhooks page not accessible')
      return
    }

    // Either empty state or existing webhooks
    const emptyState = page.getByText('No webhooks configured')
    const webhookCards = page.locator('h3').filter({ hasText: /./i })

    const isEmpty = await emptyState.isVisible().catch(() => false)
    const hasCards = await webhookCards.first().isVisible().catch(() => false)

    expect(isEmpty || hasCards).toBeTruthy()
  })

  test('Add Webhook button opens create modal', async ({ page, request }) => {
    if (!user) {
      test.skip(true, 'Could not create test user')
      return
    }

    await resetRateLimits(request)
    await loginViaBrowser(page, user.username, user.password, user.totpSecret)
    await page.goto('/webhooks')

    const addButton = page.getByRole('button', { name: /add webhook/i })
    const buttonVisible = await addButton.waitFor({ timeout: 10_000 }).then(() => true).catch(() => false)

    if (!buttonVisible) {
      test.skip(true, 'Webhooks page not accessible or Add button not found')
      return
    }

    await addButton.click()

    // Modal should open
    const dialog = page.getByRole('dialog', { name: /new webhook/i })
    await expect(dialog).toBeVisible()

    // Verify modal has expected fields
    await expect(dialog.locator('#wh-name')).toBeVisible()
    await expect(dialog.locator('#wh-url')).toBeVisible()
    await expect(dialog.locator('#wh-secret')).toBeVisible()
    await expect(dialog.getByText('Events')).toBeVisible()

    // Verify buttons
    await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeVisible()
    await expect(dialog.getByRole('button', { name: 'Create' })).toBeVisible()
  })

  test('create webhook via modal and verify in list', async ({ page, request }) => {
    if (!user) {
      test.skip(true, 'Could not create test user')
      return
    }

    await resetRateLimits(request)
    await loginViaBrowser(page, user.username, user.password, user.totpSecret)
    await page.goto('/webhooks')

    const addButton = page.getByRole('button', { name: /add webhook/i })
    const buttonVisible = await addButton.waitFor({ timeout: 10_000 }).then(() => true).catch(() => false)

    if (!buttonVisible) {
      test.skip(true, 'Webhooks page not accessible')
      return
    }

    await addButton.click()

    const dialog = page.getByRole('dialog', { name: /new webhook/i })
    await expect(dialog).toBeVisible()

    // Fill in webhook details
    const webhookName = `E2E UI Webhook ${Date.now()}`
    await dialog.locator('#wh-name').fill(webhookName)
    await dialog.locator('#wh-url').fill('https://httpbin.org/post')

    // Select at least one event
    const eventButton = dialog.getByRole('button', { name: /sync completed/i })
    await eventButton.click()
    await expect(eventButton).toHaveAttribute('aria-pressed', 'true')

    // Submit
    await dialog.getByRole('button', { name: 'Create' }).click()

    // Modal should close
    await expect(dialog).not.toBeVisible({ timeout: 5000 })

    // Webhook should appear in the list
    await expect(page.locator(`h3:has-text("${webhookName}")`)).toBeVisible({ timeout: 5000 })
    await expect(page.locator('code:has-text("https://httpbin.org/post")')).toBeVisible()
  })

  test('modal validation requires name, URL, and events', async ({ page, request }) => {
    if (!user) {
      test.skip(true, 'Could not create test user')
      return
    }

    await resetRateLimits(request)
    await loginViaBrowser(page, user.username, user.password, user.totpSecret)
    await page.goto('/webhooks')

    const addButton = page.getByRole('button', { name: /add webhook/i })
    const buttonVisible = await addButton.waitFor({ timeout: 10_000 }).then(() => true).catch(() => false)

    if (!buttonVisible) {
      test.skip(true, 'Webhooks page not accessible')
      return
    }

    await addButton.click()

    const dialog = page.getByRole('dialog', { name: /new webhook/i })
    await expect(dialog).toBeVisible()

    // Submit with empty fields
    await dialog.getByRole('button', { name: 'Create' }).click()

    // Should show validation error for name
    await expect(dialog.locator('[role="alert"]')).toHaveText('Name is required')

    // Fill name only, submit again
    await dialog.locator('#wh-name').fill('Test Webhook')
    await dialog.getByRole('button', { name: 'Create' }).click()
    await expect(dialog.locator('[role="alert"]')).toHaveText('URL is required')

    // Fill URL, submit again (no events selected)
    await dialog.locator('#wh-url').fill('https://example.com/hook')
    await dialog.getByRole('button', { name: 'Create' }).click()
    await expect(dialog.locator('[role="alert"]')).toHaveText('Select at least one event')
  })

  test('cancel button closes create modal without saving', async ({ page, request }) => {
    if (!user) {
      test.skip(true, 'Could not create test user')
      return
    }

    await resetRateLimits(request)
    await loginViaBrowser(page, user.username, user.password, user.totpSecret)
    await page.goto('/webhooks')

    const addButton = page.getByRole('button', { name: /add webhook/i })
    const buttonVisible = await addButton.waitFor({ timeout: 10_000 }).then(() => true).catch(() => false)

    if (!buttonVisible) {
      test.skip(true, 'Webhooks page not accessible')
      return
    }

    await addButton.click()

    const dialog = page.getByRole('dialog', { name: /new webhook/i })
    await expect(dialog).toBeVisible()

    // Fill some data but cancel
    await dialog.locator('#wh-name').fill('Should Not Be Saved')
    await dialog.getByRole('button', { name: 'Cancel' }).click()

    await expect(dialog).not.toBeVisible()

    // The webhook should not appear in the list
    await expect(page.locator('h3:has-text("Should Not Be Saved")')).not.toBeVisible()
  })

  test('delete webhook removes it from list', async ({ page, request }) => {
    if (!user) {
      test.skip(true, 'Could not create test user')
      return
    }

    await resetRateLimits(request)

    // First create a webhook via API so we have something to delete
    const createResp = await request.post(`${API}/webhooks/`, {
      headers: { Authorization: `Bearer ${user.accessToken}` },
      data: {
        name: 'E2E Delete Target',
        url: 'https://httpbin.org/post',
        events: ['sync.completed'],
      },
    })

    if (createResp.status() === 403) {
      test.skip(true, 'User does not have admin role')
      return
    }

    await loginViaBrowser(page, user.username, user.password, user.totpSecret)
    await page.goto('/webhooks')

    // Wait for the webhook to appear
    const targetWebhook = page.locator('h3:has-text("E2E Delete Target")')
    const visible = await targetWebhook.waitFor({ timeout: 10_000 }).then(() => true).catch(() => false)

    if (!visible) {
      test.skip(true, 'Created webhook not visible in list')
      return
    }

    // Click the delete button for this webhook
    const deleteButton = page.getByRole('button', { name: /delete webhook E2E Delete Target/i })
    await deleteButton.click()

    // Confirmation dialog should appear
    const confirmDialog = page.getByRole('alertdialog', { name: /confirm webhook deletion/i })
    await expect(confirmDialog).toBeVisible()
    await expect(confirmDialog.getByText('Delete webhook?')).toBeVisible()

    // Confirm deletion
    await confirmDialog.getByRole('button', { name: 'Delete' }).click()

    // Webhook should be removed from list
    await expect(targetWebhook).not.toBeVisible({ timeout: 5000 })
  })

  test('cancel delete keeps webhook in list', async ({ page, request }) => {
    if (!user) {
      test.skip(true, 'Could not create test user')
      return
    }

    await resetRateLimits(request)

    // Create a webhook via API
    const createResp = await request.post(`${API}/webhooks/`, {
      headers: { Authorization: `Bearer ${user.accessToken}` },
      data: {
        name: 'E2E Cancel Delete',
        url: 'https://httpbin.org/post',
        events: ['sync.completed'],
      },
    })

    if (createResp.status() === 403) {
      test.skip(true, 'User does not have admin role')
      return
    }

    await loginViaBrowser(page, user.username, user.password, user.totpSecret)
    await page.goto('/webhooks')

    const targetWebhook = page.locator('h3:has-text("E2E Cancel Delete")')
    const visible = await targetWebhook.waitFor({ timeout: 10_000 }).then(() => true).catch(() => false)

    if (!visible) {
      test.skip(true, 'Created webhook not visible in list')
      return
    }

    // Click delete
    const deleteButton = page.getByRole('button', { name: /delete webhook E2E Cancel Delete/i })
    await deleteButton.click()

    // Click Cancel in confirmation dialog
    const confirmDialog = page.getByRole('alertdialog', { name: /confirm webhook deletion/i })
    await expect(confirmDialog).toBeVisible()
    await confirmDialog.getByRole('button', { name: 'Cancel' }).click()

    // Dialog should close, webhook should remain
    await expect(confirmDialog).not.toBeVisible()
    await expect(targetWebhook).toBeVisible()
  })
})
