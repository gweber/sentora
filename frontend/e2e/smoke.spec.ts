import { test, expect } from '@playwright/test'

test.describe('Smoke tests', () => {
  test('health endpoint returns 200', async ({ request }) => {
    const response = await request.get('/api/v1/health')
    expect(response.ok()).toBeTruthy()
  })

  test('homepage loads and contains Sentora', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveTitle(/Sentora/i)
    // Verify the sidebar brand text is visible
    await expect(page.locator('text=Sentora')).toBeVisible()
  })

  test('sync page renders', async ({ page }) => {
    await page.goto('/sync')
    // The sync page should show the "SentinelOne Data Sync" heading
    await expect(page.locator('text=SentinelOne Data Sync')).toBeVisible()
  })
})
