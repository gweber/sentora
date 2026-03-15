import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useTaxonomyStore } from '@/stores/useTaxonomyStore'

vi.mock('@/api/taxonomy', () => ({
  listCategories: vi.fn(),
  getEntriesByCategory: vi.fn(),
  searchTaxonomy: vi.fn(),
  createCategory: vi.fn(),
  addEntry: vi.fn(),
  editEntry: vi.fn(),
  deleteEntry: vi.fn(),
  toggleUniversal: vi.fn(),
  updateCategory: vi.fn(),
  deleteCategory: vi.fn(),
}))

import * as taxApi from '@/api/taxonomy'
import type { CategorySummary, SoftwareEntry } from '@/types/taxonomy'

const mockCategory: CategorySummary = { key: 'browser', label: 'Browsers', entry_count: 3 }
const mockEntry: SoftwareEntry = {
  id: 'e1',
  name: 'Chrome',
  category: 'browser',
  patterns: ['chrome*'],
  universal_exclusion: false,
}

describe('useTaxonomyStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  describe('initial state', () => {
    it('starts with empty defaults', () => {
      const store = useTaxonomyStore()
      expect(store.categories).toEqual([])
      expect(store.entriesByCategory).toEqual({})
      expect(store.searchResults).toEqual([])
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
    })
  })

  describe('fetchCategories', () => {
    it('populates categories from API', async () => {
      vi.mocked(taxApi.listCategories).mockResolvedValue({ categories: [mockCategory] })

      const store = useTaxonomyStore()
      await store.fetchCategories()

      expect(store.categories).toEqual([mockCategory])
    })

    it('sets error on failure', async () => {
      vi.mocked(taxApi.listCategories).mockRejectedValue(new Error('DB down'))

      const store = useTaxonomyStore()
      await store.fetchCategories()

      expect(store.error).toBe('DB down')
    })
  })

  describe('fetchEntriesByCategory', () => {
    it('fetches and caches entries', async () => {
      vi.mocked(taxApi.getEntriesByCategory).mockResolvedValue({ entries: [mockEntry] })

      const store = useTaxonomyStore()
      await store.fetchEntriesByCategory('browser')

      expect(store.entriesByCategory['browser']).toEqual([mockEntry])
      expect(taxApi.getEntriesByCategory).toHaveBeenCalledWith('browser')
    })

    it('uses cache on second call (skips API)', async () => {
      vi.mocked(taxApi.getEntriesByCategory).mockResolvedValue({ entries: [mockEntry] })

      const store = useTaxonomyStore()
      await store.fetchEntriesByCategory('browser')
      await store.fetchEntriesByCategory('browser')

      expect(taxApi.getEntriesByCategory).toHaveBeenCalledTimes(1)
    })

    it('bypasses cache when force=true', async () => {
      vi.mocked(taxApi.getEntriesByCategory).mockResolvedValue({ entries: [mockEntry] })

      const store = useTaxonomyStore()
      await store.fetchEntriesByCategory('browser')
      await store.fetchEntriesByCategory('browser', true)

      expect(taxApi.getEntriesByCategory).toHaveBeenCalledTimes(2)
    })

    it('sets error on failure', async () => {
      vi.mocked(taxApi.getEntriesByCategory).mockRejectedValue(new Error('Not found'))

      const store = useTaxonomyStore()
      await store.fetchEntriesByCategory('nonexistent')

      expect(store.error).toBe('Not found')
    })
  })

  describe('search', () => {
    it('populates searchResults', async () => {
      vi.mocked(taxApi.searchTaxonomy).mockResolvedValue({ entries: [mockEntry] })

      const store = useTaxonomyStore()
      await store.search('chrome')

      expect(store.searchResults).toEqual([mockEntry])
    })

    it('clears searchResults for empty query', async () => {
      const store = useTaxonomyStore()
      store.searchResults = [mockEntry]

      await store.search('  ')

      expect(store.searchResults).toEqual([])
      expect(taxApi.searchTaxonomy).not.toHaveBeenCalled()
    })

    it('sets error on failure', async () => {
      vi.mocked(taxApi.searchTaxonomy).mockRejectedValue(new Error('Timeout'))

      const store = useTaxonomyStore()
      await store.search('test')

      expect(store.error).toBe('Timeout')
    })
  })

  describe('createCategory', () => {
    it('creates category and refreshes list', async () => {
      vi.mocked(taxApi.createCategory).mockResolvedValue(mockCategory)
      vi.mocked(taxApi.listCategories).mockResolvedValue({ categories: [mockCategory] })

      const store = useTaxonomyStore()
      const result = await store.createCategory({ key: 'browser', label: 'Browsers' })

      expect(result).toEqual(mockCategory)
      expect(taxApi.listCategories).toHaveBeenCalled()
    })

    it('returns null on failure', async () => {
      vi.mocked(taxApi.createCategory).mockRejectedValue(new Error('Duplicate'))

      const store = useTaxonomyStore()
      const result = await store.createCategory({ key: 'browser', label: 'Browsers' })

      expect(result).toBeNull()
      expect(store.error).toBe('Duplicate')
    })
  })

  describe('addEntry', () => {
    it('creates entry, invalidates cache, and refreshes categories', async () => {
      vi.mocked(taxApi.addEntry).mockResolvedValue(mockEntry)
      vi.mocked(taxApi.listCategories).mockResolvedValue({ categories: [mockCategory] })

      const store = useTaxonomyStore()
      store.entriesByCategory = { browser: [{ ...mockEntry, id: 'old' }] }

      const result = await store.addEntry({
        name: 'Chrome',
        category: 'browser',
        patterns: ['chrome*'],
      } as any)

      expect(result).toEqual(mockEntry)
      // Cache for 'browser' should be invalidated
      expect(store.entriesByCategory['browser']).toBeUndefined()
      expect(taxApi.listCategories).toHaveBeenCalled()
    })
  })

  describe('editEntry', () => {
    it('updates entry and invalidates category cache', async () => {
      const updatedEntry = { ...mockEntry, name: 'Chrome Updated' }
      vi.mocked(taxApi.editEntry).mockResolvedValue(updatedEntry)

      const store = useTaxonomyStore()
      store.entriesByCategory = { browser: [mockEntry] }

      const result = await store.editEntry('e1', { name: 'Chrome Updated' }, 'browser')

      expect(result).toEqual(updatedEntry)
      expect(store.entriesByCategory['browser']).toBeUndefined()
    })

    it('returns null on failure', async () => {
      vi.mocked(taxApi.editEntry).mockRejectedValue(new Error('Validation'))

      const store = useTaxonomyStore()
      const result = await store.editEntry('e1', { name: '' }, 'browser')

      expect(result).toBeNull()
      expect(store.error).toBe('Validation')
    })
  })

  describe('deleteEntry', () => {
    it('deletes entry, invalidates cache, refreshes categories', async () => {
      vi.mocked(taxApi.deleteEntry).mockResolvedValue(undefined)
      vi.mocked(taxApi.listCategories).mockResolvedValue({ categories: [] })

      const store = useTaxonomyStore()
      store.entriesByCategory = { browser: [mockEntry] }

      const result = await store.deleteEntry('e1', 'browser')

      expect(result).toBe(true)
      expect(store.entriesByCategory['browser']).toBeUndefined()
    })

    it('returns false on failure', async () => {
      vi.mocked(taxApi.deleteEntry).mockRejectedValue(new Error('Not found'))

      const store = useTaxonomyStore()
      const result = await store.deleteEntry('e1', 'browser')

      expect(result).toBe(false)
    })
  })

  describe('toggleUniversal', () => {
    it('invalidates category cache', async () => {
      vi.mocked(taxApi.toggleUniversal).mockResolvedValue(undefined as any)

      const store = useTaxonomyStore()
      store.entriesByCategory = { browser: [mockEntry] }

      await store.toggleUniversal('e1', 'browser')

      expect(store.entriesByCategory['browser']).toBeUndefined()
    })

    it('sets error on failure', async () => {
      vi.mocked(taxApi.toggleUniversal).mockRejectedValue(new Error('Failed'))

      const store = useTaxonomyStore()
      await store.toggleUniversal('e1', 'browser')

      expect(store.error).toBe('Failed')
    })
  })

  describe('updateCategory', () => {
    it('invalidates both old and new key caches on rename', async () => {
      vi.mocked(taxApi.updateCategory).mockResolvedValue({ new_key: 'web_browser' } as any)
      vi.mocked(taxApi.listCategories).mockResolvedValue({ categories: [] })

      const store = useTaxonomyStore()
      store.entriesByCategory = { browser: [mockEntry], web_browser: [] }

      const result = await store.updateCategory('browser', { key: 'web_browser', label: 'Web Browsers' })

      expect(result).toBe(true)
      expect(store.entriesByCategory['browser']).toBeUndefined()
      expect(store.entriesByCategory['web_browser']).toBeUndefined()
    })

    it('only invalidates old key when key unchanged', async () => {
      vi.mocked(taxApi.updateCategory).mockResolvedValue({ new_key: 'browser' } as any)
      vi.mocked(taxApi.listCategories).mockResolvedValue({ categories: [] })

      const store = useTaxonomyStore()
      store.entriesByCategory = { browser: [mockEntry], other: [] }

      await store.updateCategory('browser', { label: 'Browsers 2' })

      expect(store.entriesByCategory['browser']).toBeUndefined()
      // 'other' should be untouched
      expect(store.entriesByCategory['other']).toEqual([])
    })

    it('returns false on failure', async () => {
      vi.mocked(taxApi.updateCategory).mockRejectedValue(new Error('Conflict'))

      const store = useTaxonomyStore()
      const result = await store.updateCategory('browser', { label: 'x' })

      expect(result).toBe(false)
      expect(store.error).toBe('Conflict')
    })
  })

  describe('deleteCategory', () => {
    it('deletes category and invalidates cache', async () => {
      vi.mocked(taxApi.deleteCategory).mockResolvedValue(undefined as any)
      vi.mocked(taxApi.listCategories).mockResolvedValue({ categories: [] })

      const store = useTaxonomyStore()
      store.entriesByCategory = { browser: [mockEntry] }

      const result = await store.deleteCategory('browser')

      expect(result).toBe(true)
      expect(store.entriesByCategory['browser']).toBeUndefined()
    })

    it('returns false on failure', async () => {
      vi.mocked(taxApi.deleteCategory).mockRejectedValue(new Error('In use'))

      const store = useTaxonomyStore()
      const result = await store.deleteCategory('browser')

      expect(result).toBe(false)
      expect(store.error).toBe('In use')
    })
  })
})
