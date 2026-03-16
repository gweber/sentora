import { test, expect } from '@playwright/test'

/**
 * Sync lifecycle tests — verifies the sync page renders correctly,
 * handles trigger actions, and shows history. Without a real S1 API
 * token, syncs are expected to fail quickly, which is tested.
 */

test.describe('Sync lifecycle', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/sync')
    await expect(page).toHaveTitle(/Sync — Sentora/)
  })

  test('sync page renders with heading and trigger buttons', async ({ page }) => {
    await expect(page.locator('text=SentinelOne Data Sync')).toBeVisible()

    // Full sync and refresh buttons should be present
    const fullSyncButton = page.getByRole('button', { name: /start full sync/i })
    await expect(fullSyncButton).toBeVisible()

    const refreshButton = page.getByRole('button', { name: /start incremental refresh/i })
    await expect(refreshButton).toBeVisible()
  })

  test('shows initial sync status (never synced or previous state)', async ({ page }) => {
    // The status row should show either "No sync has been run yet" or a last sync time
    const statusArea = page.locator('[aria-live="polite"]')
    await expect(statusArea).toBeVisible()

    const statusText = await statusArea.textContent()
    const validStatuses = [
      'No sync has been run yet',
      'Last sync completed',
      'Last sync failed',
      'Syncing',
    ]
    const hasValidStatus = validStatuses.some((s) => statusText?.includes(s))
    expect(hasValidStatus).toBeTruthy()
  })

  test('per-phase sync buttons are rendered', async ({ page }) => {
    const phases = ['Sites', 'Groups', 'Agents', 'Applications', 'Tags']
    for (const phase of phases) {
      const phaseButton = page.getByRole('button', { name: `Sync ${phase} only` })
      await expect(phaseButton).toBeVisible()
    }
  })

  test('trigger full sync fails fast without S1 token', async ({ page }) => {
    const fullSyncButton = page.getByRole('button', { name: /start full sync/i })
    await fullSyncButton.click()

    // Without an S1 API token configured, the sync should fail quickly
    // or show a running state that resolves to failed. Wait for either
    // "failed" status or an error count to appear.
    const failedOrError = page.locator('text=failed, text=error')
    await expect(failedOrError.first()).toBeVisible({ timeout: 15000 })
  })

  test('sync history section exists', async ({ page }) => {
    // The "Sync History" heading should be present
    await expect(page.getByText('Sync History')).toBeVisible()

    // It should either show "No sync history yet" or a table of runs
    const noHistory = page.locator('text=No sync history yet')
    const historyTable = page.locator('table')

    const hasNoHistory = await noHistory.isVisible().catch(() => false)
    const hasTable = await historyTable.isVisible().catch(() => false)

    expect(hasNoHistory || hasTable).toBeTruthy()
  })

  test('sync history table has expected columns when runs exist', async ({ page }) => {
    const historyTable = page.locator('table').last()
    const hasTable = await historyTable.isVisible().catch(() => false)

    if (!hasTable) {
      test.skip(true, 'No sync history table — no runs recorded yet')
      return
    }

    // Verify column headers
    const expectedHeaders = ['Started', 'Mode', 'Phases', 'Status', 'Groups', 'Agents', 'Apps', 'Tags', 'Errors']
    for (const header of expectedHeaders) {
      await expect(historyTable.locator(`th:has-text("${header}")`)).toBeVisible()
    }
  })

  test('progress bars are present with proper ARIA roles', async ({ page }) => {
    // Progress bars should be rendered (even if at 0% or showing "done")
    const progressBars = page.locator('[role="progressbar"]')
    const count = await progressBars.count()

    // There should be 5 progress bars (sites, groups, agents, apps, tags)
    // or 0 if the "Trigger a sync to see live progress" placeholder is shown
    if (count > 0) {
      expect(count).toBe(5)
      // Each should have aria-valuemin and aria-valuemax
      for (let i = 0; i < count; i++) {
        await expect(progressBars.nth(i)).toHaveAttribute('aria-valuemin', '0')
        await expect(progressBars.nth(i)).toHaveAttribute('aria-valuemax', '100')
      }
    } else {
      // Placeholder text should be visible instead
      await expect(page.locator('text=Trigger a sync to see live progress')).toBeVisible()
    }
  })

  test('data maintenance section is present', async ({ page }) => {
    await expect(page.getByText('Data Maintenance')).toBeVisible()
    await expect(page.getByRole('button', { name: /run app names backfill/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /re-normalize app names/i })).toBeVisible()
  })

  test('fetch limits section is present with inputs', async ({ page }) => {
    await expect(page.getByText('Fetch Limits')).toBeVisible()

    // Wait for the limits to load
    const agentsInput = page.getByLabel('Page size for agents')
    await expect(agentsInput).toBeVisible({ timeout: 5000 })

    const appsInput = page.getByLabel('Page size for installed apps')
    await expect(appsInput).toBeVisible()

    const saveButton = page.getByRole('button', { name: /save fetch limits/i })
    await expect(saveButton).toBeVisible()
  })
})
