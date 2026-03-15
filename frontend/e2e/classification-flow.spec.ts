import { test, expect } from '@playwright/test'

/**
 * Classification flow tests — verifies the classification page renders,
 * handles empty state gracefully, tests filter pills, and trigger button.
 */

test.describe('Classification flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/classification')
    await expect(page).toHaveTitle(/Classification — Sentora/)
  })

  test('page renders with overview stat cards', async ({ page }) => {
    // Verdict stat cards should be present
    const verdicts = ['correct', 'misclassified', 'ambiguous', 'unclassifiable']
    for (const verdict of verdicts) {
      await expect(page.locator(`text=${verdict}`).first()).toBeVisible({ timeout: 5000 })
    }

    // Total card
    await expect(page.getByText('Total').first()).toBeVisible()
  })

  test('run classification button is present and labeled', async ({ page }) => {
    const runButton = page.getByRole('button', { name: /run classification/i })
    await expect(runButton).toBeVisible()
  })

  test('trigger classification handles empty/error state gracefully', async ({ page }) => {
    const runButton = page.getByRole('button', { name: /run classification/i })
    await runButton.click()

    // After clicking, the button text should change to "Running..." or
    // the classification should complete quickly (no data to classify).
    // Either way, the page should not crash.
    // Wait for the async operation to settle — either the button returns
    // to its normal state or the page content remains intact.
    await page.waitForLoadState('networkidle')

    // The page should still be functional — run button should be re-enabled
    // or showing an error message, but the page structure remains intact.
    const pageContent = page.locator('main[aria-label="Page content"]')
    await expect(pageContent).toBeVisible()

    // The run button should eventually return to its normal state
    await expect(runButton).toBeVisible({ timeout: 10000 })
  })

  test('filter pills are present and interactive', async ({ page }) => {
    // "All" pill should be active by default
    const allPill = page.getByRole('button', { name: 'All' }).filter({ has: page.locator('[aria-pressed]') })
    // Use a more resilient check — find the All button
    const allButton = page.getByRole('button', { name: 'All', exact: true })
    await expect(allButton).toBeVisible()
    await expect(allButton).toHaveAttribute('aria-pressed', 'true')

    // Verdict filter pills
    const verdicts = ['correct', 'misclassified', 'ambiguous', 'unclassifiable']
    for (const verdict of verdicts) {
      const pill = page.getByRole('button', { name: verdict, exact: true })
      await expect(pill).toBeVisible()
      await expect(pill).toHaveAttribute('aria-pressed', 'false')
    }
  })

  test('clicking a verdict pill activates it and deactivates All', async ({ page }) => {
    const correctPill = page.getByRole('button', { name: 'correct', exact: true })
    await correctPill.click()

    // "correct" should now be active
    await expect(correctPill).toHaveAttribute('aria-pressed', 'true')

    // "All" should be inactive
    const allButton = page.getByRole('button', { name: 'All', exact: true })
    await expect(allButton).toHaveAttribute('aria-pressed', 'false')
  })

  test('clicking through each filter pill works', async ({ page }) => {
    const verdicts = ['correct', 'misclassified', 'ambiguous', 'unclassifiable']

    for (const verdict of verdicts) {
      const pill = page.getByRole('button', { name: verdict, exact: true })
      await pill.click()
      await expect(pill).toHaveAttribute('aria-pressed', 'true')

      // All other pills should be inactive
      for (const other of verdicts.filter((v) => v !== verdict)) {
        const otherPill = page.getByRole('button', { name: other, exact: true })
        await expect(otherPill).toHaveAttribute('aria-pressed', 'false')
      }
    }

    // Click "All" to reset
    const allButton = page.getByRole('button', { name: 'All', exact: true })
    await allButton.click()
    await expect(allButton).toHaveAttribute('aria-pressed', 'true')
  })

  test('search input is present and labeled', async ({ page }) => {
    const searchInput = page.getByLabel('Search classification results by hostname')
    await expect(searchInput).toBeVisible()
    await expect(searchInput).toHaveAttribute('placeholder', 'Search hostname…')
  })

  test('export buttons are present', async ({ page }) => {
    const csvButton = page.getByRole('button', { name: /export results as csv/i })
    await expect(csvButton).toBeVisible()

    const jsonButton = page.getByRole('button', { name: /export results as json/i })
    await expect(jsonButton).toBeVisible()
  })

  test('empty state shows helpful message when no results', async ({ page }) => {
    // If no classification has been run, the empty state should appear
    const emptyState = page.getByText('No results yet')
    const hasResults = page.locator('table tbody tr').first()

    const showsEmpty = await emptyState.isVisible().catch(() => false)
    const showsResults = await hasResults.isVisible().catch(() => false)

    // One of these must be true — either results or empty state
    expect(showsEmpty || showsResults).toBeTruthy()

    if (showsEmpty) {
      await expect(
        page.getByText('Configure fingerprints and click "Run Classification" to get started'),
      ).toBeVisible()
    }
  })

  test('results table has expected columns when data exists', async ({ page }) => {
    const table = page.locator('table').first()
    const hasTable = await table.isVisible().catch(() => false)

    if (!hasTable) {
      test.skip(true, 'No classification results to verify table structure')
      return
    }

    const expectedHeaders = [
      'Hostname',
      'Group',
      'Verdict',
      'Suggested',
      'Top Score',
      'Computed',
      'Actions',
    ]
    for (const header of expectedHeaders) {
      await expect(table.locator(`th:has-text("${header}")`)).toBeVisible()
    }
  })

  test('page handles loading state without crashing', async ({ page }) => {
    // Verify the page structure is intact even during/after API calls
    const mainContent = page.locator('main[aria-label="Page content"]')
    await expect(mainContent).toBeVisible()

    // The page should have the classification-specific elements
    await expect(page.getByRole('button', { name: /run classification/i })).toBeVisible()
    await expect(page.getByRole('button', { name: 'All', exact: true })).toBeVisible()
  })
})
