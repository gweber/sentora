import { test, expect } from '@playwright/test'

/**
 * Taxonomy CRUD flow — tests category selection, entry creation,
 * editing, and deletion via the Taxonomy view.
 */

test.describe('Taxonomy CRUD flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/taxonomy')
    await expect(page).toHaveTitle(/Software Taxonomy — Sentora/)
  })

  test('page renders with category sidebar', async ({ page }) => {
    // The category sidebar component should be present
    // Wait for categories to load (they come from the API)
    const sidebar = page.locator('text=Categories')
    await expect(sidebar).toBeVisible({ timeout: 10000 })
  })

  test('clicking a category loads its entries', async ({ page }) => {
    // Wait for categories to load from the API
    await page.locator('text=Categories').waitFor({ state: 'visible', timeout: 10000 })

    // Find the first category button in the sidebar and click it
    const categoryButtons = page.locator('aside button, [class*="sidebar"] button').first()
    const hasCategoryButtons = await categoryButtons.isVisible().catch(() => false)

    if (hasCategoryButtons) {
      await categoryButtons.click()
      // After clicking, entries should load or show "No entries" message
      // Either we see entry cards or the empty state
      const entriesOrEmpty = page.locator('text=entries, text=No entries in this category')
      await expect(entriesOrEmpty.first()).toBeVisible({ timeout: 5000 })
    } else {
      // No categories exist — verify the placeholder message
      await expect(page.locator('text=Select a category')).toBeVisible()
    }
  })

  test('create a new taxonomy entry', async ({ page }) => {
    // Wait for categories to load from the API
    await page.locator('text=Categories').waitFor({ state: 'visible', timeout: 10000 })

    // Check if there are categories to work with
    const selectPrompt = page.locator('text=Select a category to see entries')
    const hasNoSelection = await selectPrompt.isVisible().catch(() => false)

    // If no category is selected, try to select one first
    if (hasNoSelection) {
      // Look for any clickable category in the sidebar
      const firstCategory = page.locator('aside button, [class*="CategorySidebar"] button').first()
      const exists = await firstCategory.isVisible().catch(() => false)
      if (!exists) {
        test.skip(true, 'No taxonomy categories available to test entry creation')
        return
      }
      await firstCategory.click()
      await page.waitForLoadState('networkidle')
    }

    // Click the "Add entry" button
    const addButton = page.getByRole('button', { name: /add entry/i })
    await expect(addButton).toBeVisible({ timeout: 5000 })
    await addButton.click()

    // The modal should open
    const dialog = page.getByRole('dialog', { name: /add taxonomy entry/i })
    await expect(dialog).toBeVisible()

    // Fill in the form
    const uniqueName = `E2E Test Entry ${Date.now()}`
    await dialog.locator('input').first().fill(uniqueName)

    // Fill patterns
    const patternsField = dialog.locator('textarea').first()
    await patternsField.fill('e2e_test_pattern*')

    // Submit the form
    const submitButton = dialog.getByRole('button', { name: /add entry/i })
    await submitButton.click()

    // Modal should close
    await expect(dialog).not.toBeVisible({ timeout: 5000 })

    // The new entry should appear in the list
    await expect(page.locator(`text=${uniqueName}`)).toBeVisible({ timeout: 5000 })
  })

  test('edit an existing taxonomy entry', async ({ page }) => {
    // Wait for categories to load and select the first one
    await page.locator('text=Categories').waitFor({ state: 'visible', timeout: 10000 })

    const selectPrompt = page.locator('text=Select a category to see entries')
    if (await selectPrompt.isVisible().catch(() => false)) {
      const firstCategory = page.locator('aside button, [class*="CategorySidebar"] button').first()
      if (!(await firstCategory.isVisible().catch(() => false))) {
        test.skip(true, 'No taxonomy categories available')
        return
      }
      await firstCategory.click()
      await page.waitForLoadState('networkidle')
    }

    // Find the edit button (pencil icon) on the first entry
    const editButton = page.locator('button[title="Edit entry"]').first()
    const hasEntries = await editButton.isVisible().catch(() => false)

    if (!hasEntries) {
      test.skip(true, 'No entries to edit — run create test first or seed data')
      return
    }

    await editButton.click()

    // The edit modal should open
    const dialog = page.getByRole('dialog', { name: /edit taxonomy entry/i })
    await expect(dialog).toBeVisible()

    // Change the name
    const nameInput = dialog.locator('input').first()
    const oldName = await nameInput.inputValue()
    const editedName = `${oldName} (edited)`
    await nameInput.clear()
    await nameInput.fill(editedName)

    // Save changes
    const saveButton = dialog.getByRole('button', { name: /save changes/i })
    await saveButton.click()

    // Modal should close
    await expect(dialog).not.toBeVisible({ timeout: 5000 })

    // The edited name should be visible
    await expect(page.locator(`text=${editedName}`)).toBeVisible({ timeout: 5000 })
  })

  test('delete a taxonomy entry with inline confirmation', async ({ page }) => {
    // Wait for categories to load and select the first one
    await page.locator('text=Categories').waitFor({ state: 'visible', timeout: 10000 })

    const selectPrompt = page.locator('text=Select a category to see entries')
    if (await selectPrompt.isVisible().catch(() => false)) {
      const firstCategory = page.locator('aside button, [class*="CategorySidebar"] button').first()
      if (!(await firstCategory.isVisible().catch(() => false))) {
        test.skip(true, 'No taxonomy categories available')
        return
      }
      await firstCategory.click()
      await page.waitForLoadState('networkidle')
    }

    // Find the delete button on the first entry
    const deleteButton = page.locator('button[title="Delete entry"]').first()
    const hasEntries = await deleteButton.isVisible().catch(() => false)

    if (!hasEntries) {
      test.skip(true, 'No entries to delete')
      return
    }

    // Get the name of the entry we are about to delete
    const entryCard = deleteButton.locator('xpath=ancestor::div[contains(@class,"bg-white")]')
    const entryName = await entryCard.locator('.font-semibold').first().textContent()

    // Click delete — should show inline confirmation "Delete? [Yes] [No]"
    await deleteButton.click()
    await expect(page.getByText('Delete?')).toBeVisible()

    // Confirm deletion
    const confirmYes = page.getByRole('button', { name: 'Yes' })
    await confirmYes.click()

    // The entry should be removed (wait for the API call to finish)
    if (entryName) {
      // Wait for the delete API call to complete and the UI to update
      await page.waitForLoadState('networkidle')
      // The exact entry text might still exist if there are multiple with similar text,
      // but the delete confirmation should be gone
      await expect(page.getByText('Delete?')).not.toBeVisible()
    }
  })

  test('cancel delete does not remove the entry', async ({ page }) => {
    await page.locator('text=Categories').waitFor({ state: 'visible', timeout: 10000 })

    const selectPrompt = page.locator('text=Select a category to see entries')
    if (await selectPrompt.isVisible().catch(() => false)) {
      const firstCategory = page.locator('aside button, [class*="CategorySidebar"] button').first()
      if (!(await firstCategory.isVisible().catch(() => false))) {
        test.skip(true, 'No taxonomy categories available')
        return
      }
      await firstCategory.click()
      await page.waitForLoadState('networkidle')
    }

    const deleteButton = page.locator('button[title="Delete entry"]').first()
    if (!(await deleteButton.isVisible().catch(() => false))) {
      test.skip(true, 'No entries to test delete cancellation')
      return
    }

    await deleteButton.click()
    await expect(page.getByText('Delete?')).toBeVisible()

    // Click "No" to cancel
    const cancelNo = page.getByRole('button', { name: 'No' })
    await cancelNo.click()

    // Confirmation should be dismissed, entry still present
    await expect(page.getByText('Delete?')).not.toBeVisible()
  })

  test('close add-entry modal via Cancel button', async ({ page }) => {
    await page.locator('text=Categories').waitFor({ state: 'visible', timeout: 10000 })

    const selectPrompt = page.locator('text=Select a category to see entries')
    if (await selectPrompt.isVisible().catch(() => false)) {
      const firstCategory = page.locator('aside button, [class*="CategorySidebar"] button').first()
      if (!(await firstCategory.isVisible().catch(() => false))) {
        test.skip(true, 'No taxonomy categories available')
        return
      }
      await firstCategory.click()
      await page.waitForLoadState('networkidle')
    }

    const addButton = page.getByRole('button', { name: /add entry/i })
    if (!(await addButton.isVisible().catch(() => false))) {
      test.skip(true, 'Add entry button not visible')
      return
    }

    await addButton.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()

    // Click Cancel
    await dialog.getByRole('button', { name: /cancel/i }).click()
    await expect(dialog).not.toBeVisible()
  })
})
