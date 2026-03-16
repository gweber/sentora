/**
 * Taxonomy store.
 *
 * Caches taxonomy categories and entries. Entries are loaded per-category
 * on demand to avoid fetching the entire catalog at startup.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as taxonomyApi from '@/api/taxonomy'
import type {
  CategoryCreateRequest,
  CategorySummary,
  CategoryUpdateRequest,
  SoftwareEntry,
  SoftwareEntryCreateRequest,
  SoftwareEntryUpdateRequest,
} from '@/types/taxonomy'

export const useTaxonomyStore = defineStore('taxonomy', () => {
  const categories = ref<CategorySummary[]>([])
  const entriesByCategory = ref<Record<string, SoftwareEntry[]>>({})
  const searchResults = ref<SoftwareEntry[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  /** Load all taxonomy categories. */
  async function fetchCategories(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      const response = await taxonomyApi.listCategories()
      categories.value = response.categories
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load categories'
    } finally {
      isLoading.value = false
    }
  }

  /** Load entries for a specific category (cached after first load). */
  async function fetchEntriesByCategory(category: string, force = false): Promise<void> {
    if (!force && entriesByCategory.value[category]) return
    isLoading.value = true
    error.value = null
    try {
      const response = await taxonomyApi.getEntriesByCategory(category)
      entriesByCategory.value = { ...entriesByCategory.value, [category]: response.entries }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load entries'
    } finally {
      isLoading.value = false
    }
  }

  /** Search entries by name. */
  async function search(query: string): Promise<void> {
    if (!query.trim()) {
      searchResults.value = []
      return
    }
    isLoading.value = true
    error.value = null
    try {
      const response = await taxonomyApi.searchTaxonomy(query)
      searchResults.value = response.entries
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Search failed'
    } finally {
      isLoading.value = false
    }
  }

  /** Create a new taxonomy category (first-class, no placeholder entry needed). */
  async function createCategory(payload: CategoryCreateRequest): Promise<CategorySummary | null> {
    isLoading.value = true
    error.value = null
    try {
      const cat = await taxonomyApi.createCategory(payload)
      await fetchCategories()
      return cat
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to create category'
      return null
    } finally {
      isLoading.value = false
    }
  }

  /** Create a new taxonomy entry and refresh its category. */
  async function addEntry(payload: SoftwareEntryCreateRequest): Promise<SoftwareEntry | null> {
    isLoading.value = true
    error.value = null
    try {
      const entry = await taxonomyApi.addEntry(payload)
      // Invalidate the category cache so it re-fetches
      delete entriesByCategory.value[payload.category]
      await fetchCategories()
      return entry
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to add entry'
      return null
    } finally {
      isLoading.value = false
    }
  }

  /** Update a taxonomy entry. */
  async function editEntry(
    entryId: string,
    payload: SoftwareEntryUpdateRequest,
    category: string,
  ): Promise<SoftwareEntry | null> {
    isLoading.value = true
    error.value = null
    try {
      const entry = await taxonomyApi.editEntry(entryId, payload)
      // Invalidate cache and re-fetch so the UI reflects the update
      delete entriesByCategory.value[category]
      await fetchEntriesByCategory(category, true)
      return entry
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update entry'
      return null
    } finally {
      isLoading.value = false
    }
  }

  /** Delete a taxonomy entry. */
  async function deleteEntry(entryId: string, category: string): Promise<boolean> {
    isLoading.value = true
    error.value = null
    try {
      await taxonomyApi.deleteEntry(entryId)
      delete entriesByCategory.value[category]
      await fetchCategories()
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to delete entry'
      return false
    } finally {
      isLoading.value = false
    }
  }

  /** Toggle the universal exclusion flag. */
  async function toggleUniversal(entryId: string, category: string): Promise<void> {
    try {
      await taxonomyApi.toggleUniversal(entryId)
      delete entriesByCategory.value[category]
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to toggle universal flag'
    }
  }

  /** Rename a category's key and/or display label. */
  async function updateCategory(categoryKey: string, payload: CategoryUpdateRequest): Promise<boolean> {
    isLoading.value = true
    error.value = null
    try {
      const result = await taxonomyApi.updateCategory(categoryKey, payload)
      // Invalidate old key cache and the new key if different
      delete entriesByCategory.value[categoryKey]
      if (result.new_key !== categoryKey) {
        delete entriesByCategory.value[result.new_key]
      }
      await fetchCategories()
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to rename category'
      return false
    } finally {
      isLoading.value = false
    }
  }

  /** Delete a category and all its entries. */
  async function deleteCategory(categoryKey: string): Promise<boolean> {
    isLoading.value = true
    error.value = null
    try {
      await taxonomyApi.deleteCategory(categoryKey)
      delete entriesByCategory.value[categoryKey]
      await fetchCategories()
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to delete category'
      return false
    } finally {
      isLoading.value = false
    }
  }

  return {
    categories,
    entriesByCategory,
    searchResults,
    isLoading,
    error,
    fetchCategories,
    fetchEntriesByCategory,
    search,
    createCategory,
    addEntry,
    editEntry,
    deleteEntry,
    toggleUniversal,
    updateCategory,
    deleteCategory,
  }
})
