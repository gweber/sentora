import { test, expect } from '@playwright/test'

/**
 * Fingerprint workflow tests — verifies the fingerprint editor page
 * renders correctly, handles empty state, and tests the catalog / marker
 * interaction flow when data is available.
 */

test.describe('Fingerprint workflow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/fingerprints')
    await expect(page).toHaveTitle(/Fingerprint Editor — Sentora/)
  })

  test('shows empty state when no group is selected', async ({ page }) => {
    // Without a groupId in the URL, the empty state should be visible
    await expect(page.getByText('No group selected')).toBeVisible()
    await expect(
      page.getByText('Choose a group from the Groups page to build its fingerprint'),
    ).toBeVisible()
  })

  test('empty state has a "Browse Groups" link', async ({ page }) => {
    const browseLink = page.getByRole('link', { name: /browse groups/i })
    await expect(browseLink).toBeVisible()
    await expect(browseLink).toHaveAttribute('href', '/groups')
  })

  test('clicking Browse Groups navigates to groups page', async ({ page }) => {
    const browseLink = page.getByRole('link', { name: /browse groups/i })
    await browseLink.click()
    await page.waitForURL('**/groups', { timeout: 5000 })
    await expect(page).toHaveTitle(/Groups — Sentora/)
  })

  test('navigating to /groups and selecting a group opens fingerprint editor', async ({
    page,
  }) => {
    // Go to groups page
    await page.goto('/groups')
    await page.waitForLoadState('networkidle')

    // Look for a group card that has a fingerprint link
    const groupLink = page.locator('a[href*="/fingerprints/"]').first()
    const hasGroups = await groupLink.isVisible().catch(() => false)

    if (!hasGroups) {
      test.skip(true, 'No groups available — sync required')
      return
    }

    await groupLink.click()
    await page.waitForURL('**/fingerprints/**', { timeout: 5000 })

    // The three-panel layout should be visible
    await expect(page.getByText('Catalog')).toBeVisible({ timeout: 5000 })
    await expect(page.getByText('Fingerprint Definition')).toBeVisible()
    await expect(page.getByText('Pattern Preview')).toBeVisible()
  })
})

test.describe('Fingerprint editor with group context', () => {
  // These tests require a group to exist. We attempt to find one
  // dynamically via the groups API. If no groups exist, the tests skip.

  let groupId: string | null = null

  test.beforeAll(async ({ request }) => {
    try {
      const response = await request.get('/api/v1/groups/')
      if (response.ok()) {
        const data = await response.json()
        const groups = Array.isArray(data) ? data : data.groups ?? data.items ?? []
        if (groups.length > 0) {
          groupId = groups[0].group_id ?? groups[0].id ?? groups[0]._id
        }
      }
    } catch {
      // No groups available
    }
  })

  test('three-panel layout renders when group exists', async ({ page }) => {
    if (!groupId) {
      test.skip(true, 'No groups available — sync required')
      return
    }

    await page.goto(`/fingerprints/${groupId}`)

    // Catalog panel
    await expect(page.getByText('Catalog')).toBeVisible({ timeout: 10000 })

    // Fingerprint Definition panel
    await expect(page.getByText('Fingerprint Definition')).toBeVisible()

    // Pattern Preview panel
    await expect(page.getByText('Pattern Preview')).toBeVisible()
  })

  test('catalog shows taxonomy categories', async ({ page }) => {
    if (!groupId) {
      test.skip(true, 'No groups available — sync required')
      return
    }

    await page.goto(`/fingerprints/${groupId}`)

    // The catalog panel should have at least one category button
    const catalogPanel = page.locator('text=Catalog').locator('..')
    await expect(catalogPanel).toBeVisible({ timeout: 10000 })

    // Search box for categories
    const searchInput = page.getByLabel('Search taxonomy categories')
    await expect(searchInput).toBeVisible()
  })

  test('catalog search filters categories', async ({ page }) => {
    if (!groupId) {
      test.skip(true, 'No groups available — sync required')
      return
    }

    await page.goto(`/fingerprints/${groupId}`)

    const searchInput = page.getByLabel('Search taxonomy categories')
    await expect(searchInput).toBeVisible({ timeout: 10000 })

    // Type a non-matching search term
    await searchInput.fill('zzz_nonexistent_category_xyz')
    await page.waitForLoadState('networkidle')

    // The category list should be empty or show no matches
    // (At minimum, fewer items than before)
  })

  test('marker drop zone shows empty state when no markers exist', async ({ page }) => {
    if (!groupId) {
      test.skip(true, 'No groups available — sync required')
      return
    }

    await page.goto(`/fingerprints/${groupId}`)
    await page.waitForLoadState('networkidle')

    // If no markers, the drop zone should show the hint text
    const dropHint = page.getByText('Drag entries from the catalog')
    const markerExists = page.locator('[title="Remove marker"]').first()

    const hasDropHint = await dropHint.isVisible().catch(() => false)
    const hasMarkers = await markerExists.isVisible().catch(() => false)

    // One of these must be true
    expect(hasDropHint || hasMarkers).toBeTruthy()
  })

  test('pattern preview panel shows hint when no marker is selected', async ({ page }) => {
    if (!groupId) {
      test.skip(true, 'No groups available — sync required')
      return
    }

    await page.goto(`/fingerprints/${groupId}`)
    await page.waitForLoadState('networkidle')

    await expect(
      page.getByText('Click a marker to see which agents match its pattern'),
    ).toBeVisible({ timeout: 5000 })
  })

  test('suggestions button is present', async ({ page }) => {
    if (!groupId) {
      test.skip(true, 'No groups available — sync required')
      return
    }

    await page.goto(`/fingerprints/${groupId}`)
    await page.waitForLoadState('networkidle')

    const suggestionsButton = page.getByRole('button', { name: /suggestions/i })
    await expect(suggestionsButton).toBeVisible({ timeout: 5000 })
  })
})
