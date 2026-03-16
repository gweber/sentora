import { test, expect } from '@playwright/test'

/**
 * Navigation flow tests — verifies sidebar links, active state,
 * page title updates, and basic route rendering.
 */

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/dashboard', title: 'Dashboard' },
  { label: 'Groups', path: '/groups', title: 'Groups' },
  { label: 'Applications', path: '/apps', title: 'Applications' },
  { label: 'Taxonomy', path: '/taxonomy', title: 'Software Taxonomy' },
  { label: 'Tag Rules', path: '/tags', title: 'Tag Rules' },
  { label: 'Fingerprint Editor', path: '/fingerprints', title: 'Fingerprint Editor' },
  { label: 'Proposals', path: '/fingerprints/proposals', title: 'Fingerprint Proposals' },
  { label: 'Classification', path: '/classification', title: 'Classification' },
  { label: 'Anomalies', path: '/anomalies', title: 'Anomalies' },
  { label: 'Settings', path: '/settings', title: 'Settings' },
  { label: 'Sync', path: '/sync', title: 'Sync' },
  { label: 'Audit Log', path: '/audit', title: 'Audit Log' },
  { label: 'Getting Started', path: '/guide', title: 'Getting Started' },
]

test.describe('Navigation flow', () => {
  test('all sidebar nav links navigate and render without error', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page.locator('text=Sentora')).toBeVisible()

    for (const item of NAV_ITEMS) {
      const link = page.locator(`nav[aria-label="Primary"] a[aria-label="${item.label}"]`)
      // Some links might not be visible if scrolled — force click
      await link.click({ force: true })
      // Wait for the route to settle
      await page.waitForURL(`**${item.path}`, { timeout: 5000 })
      // The page should not show a blank/error screen — the main content area should exist
      await expect(page.locator('main[aria-label="Page content"]')).toBeVisible()
    }
  })

  test('active nav item has aria-current="page"', async ({ page }) => {
    for (const item of NAV_ITEMS.slice(0, 5)) {
      await page.goto(item.path)
      const link = page.locator(`nav[aria-label="Primary"] a[aria-label="${item.label}"]`)
      await expect(link).toHaveAttribute('aria-current', 'page')
    }
  })

  test('non-active nav items do not have aria-current', async ({ page }) => {
    await page.goto('/dashboard')
    // Sync is in bottomNav, should not be active on /dashboard
    const syncLink = page.locator('nav[aria-label="Primary"] a[aria-label="Sync"]')
    await expect(syncLink).not.toHaveAttribute('aria-current', 'page')
  })

  test('page title updates on navigation', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page).toHaveTitle(/Dashboard — Sentora/)

    await page.goto('/sync')
    await expect(page).toHaveTitle(/Sync — Sentora/)

    await page.goto('/taxonomy')
    await expect(page).toHaveTitle(/Software Taxonomy — Sentora/)

    await page.goto('/classification')
    await expect(page).toHaveTitle(/Classification — Sentora/)
  })

  test('topbar shows the current page label', async ({ page }) => {
    await page.goto('/dashboard')
    const topbar = page.locator('header h1')
    await expect(topbar).toHaveText('Dashboard')

    await page.goto('/taxonomy')
    await expect(topbar).toHaveText('Taxonomy')
  })

  test('root path redirects to /dashboard', async ({ page }) => {
    await page.goto('/')
    await page.waitForURL('**/dashboard', { timeout: 5000 })
    await expect(page).toHaveTitle(/Dashboard — Sentora/)
  })

  test('unknown path redirects to /dashboard', async ({ page }) => {
    await page.goto('/nonexistent-page-xyz')
    await page.waitForURL('**/dashboard', { timeout: 5000 })
    await expect(page).toHaveTitle(/Dashboard — Sentora/)
  })

  test('sidebar brand is always visible', async ({ page }) => {
    await page.goto('/dashboard')
    const brand = page.locator('aside[aria-label="Main navigation"]')
    await expect(brand.locator('text=Sentora')).toBeVisible()
    await expect(brand.locator('text=EDR Asset Classification')).toBeVisible()
  })
})
