import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useTagStore } from '@/stores/useTagStore'

vi.mock('@/api/tags', () => ({
  listRules: vi.fn(),
  getRule: vi.fn(),
  createRule: vi.fn(),
  updateRule: vi.fn(),
  deleteRule: vi.fn(),
  addPattern: vi.fn(),
  removePattern: vi.fn(),
  previewRule: vi.fn(),
  applyRule: vi.fn(),
}))

import * as tagsApi from '@/api/tags'
import type { TagRule, TagRulePattern } from '@/types/tags'

const mockPattern: TagRulePattern = {
  id: 'p1',
  pattern: 'chrome*',
  display_name: 'Chrome',
  category: 'browser',
  source: 'manual',
  added_at: '2025-01-01T00:00:00Z',
  added_by: 'admin',
}

const mockRule: TagRule = {
  id: 'r1',
  tag_name: 'Browser Rule',
  description: '',
  patterns: [mockPattern],
  apply_status: 'idle',
  last_applied_at: null,
  last_applied_count: 0,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  created_by: 'admin',
}

describe('useTagStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  describe('initial state', () => {
    it('starts with empty defaults', () => {
      const store = useTagStore()
      expect(store.rules).toEqual([])
      expect(store.activeRule).toBeNull()
      expect(store.previewResult).toBeNull()
      expect(store.isLoading).toBe(false)
      expect(store.isPreviewLoading).toBe(false)
      expect(store.isApplying).toBe(false)
      expect(store.error).toBeNull()
    })
  })

  describe('fetchRules', () => {
    it('populates rules from API', async () => {
      vi.mocked(tagsApi.listRules).mockResolvedValue([mockRule])

      const store = useTagStore()
      await store.fetchRules()

      expect(store.rules).toEqual([mockRule])
      expect(store.isLoading).toBe(false)
    })

    it('sets error on failure', async () => {
      vi.mocked(tagsApi.listRules).mockRejectedValue(new Error('Network'))

      const store = useTagStore()
      await store.fetchRules()

      expect(store.error).toBe('Network')
    })
  })

  describe('loadRule', () => {
    it('sets activeRule and clears previewResult', async () => {
      vi.mocked(tagsApi.getRule).mockResolvedValue(mockRule)

      const store = useTagStore()
      store.previewResult = { matched_count: 5 } as any

      await store.loadRule('r1')

      expect(store.activeRule).toEqual(mockRule)
      expect(store.previewResult).toBeNull()
    })

    it('sets activeRule to null and error on failure', async () => {
      vi.mocked(tagsApi.getRule).mockRejectedValue(new Error('Not found'))

      const store = useTagStore()
      store.activeRule = mockRule

      await store.loadRule('bad-id')

      expect(store.activeRule).toBeNull()
      expect(store.error).toBe('Not found')
    })
  })

  describe('createRule', () => {
    it('creates rule and appends to rules list', async () => {
      vi.mocked(tagsApi.createRule).mockResolvedValue(mockRule)

      const store = useTagStore()
      const result = await store.createRule({ name: 'Browser Rule', tag_key: 'browser', tag_value: 'true' } as any)

      expect(result).toEqual(mockRule)
      expect(store.rules).toHaveLength(1)
    })

    it('returns null on failure', async () => {
      vi.mocked(tagsApi.createRule).mockRejectedValue(new Error('Validation'))

      const store = useTagStore()
      const result = await store.createRule({ name: '' } as any)

      expect(result).toBeNull()
      expect(store.error).toBe('Validation')
    })
  })

  describe('updateRule', () => {
    it('updates activeRule and rules list entry', async () => {
      const updated = { ...mockRule, tag_name: 'Updated Rule' }
      vi.mocked(tagsApi.updateRule).mockResolvedValue(updated)

      const store = useTagStore()
      store.rules = [mockRule]
      store.activeRule = mockRule

      await store.updateRule('r1', { tag_name: 'Updated Rule' })

      expect(store.activeRule!.tag_name).toBe('Updated Rule')
      expect(store.rules[0]!.tag_name).toBe('Updated Rule')
    })

    it('sets error on failure', async () => {
      vi.mocked(tagsApi.updateRule).mockRejectedValue(new Error('Bad request'))

      const store = useTagStore()
      await store.updateRule('r1', { tag_name: '' })

      expect(store.error).toBe('Bad request')
    })
  })

  describe('deleteRule', () => {
    it('removes rule from list and clears activeRule if matching', async () => {
      vi.mocked(tagsApi.deleteRule).mockResolvedValue(undefined)

      const store = useTagStore()
      store.rules = [mockRule]
      store.activeRule = mockRule

      await store.deleteRule('r1')

      expect(store.rules).toEqual([])
      expect(store.activeRule).toBeNull()
    })

    it('preserves activeRule if different rule deleted', async () => {
      vi.mocked(tagsApi.deleteRule).mockResolvedValue(undefined)

      const store = useTagStore()
      store.rules = [mockRule, { ...mockRule, id: 'r2' }]
      store.activeRule = mockRule

      await store.deleteRule('r2')

      expect(store.activeRule).toEqual(mockRule)
      expect(store.rules).toHaveLength(1)
    })

    it('sets error on failure', async () => {
      vi.mocked(tagsApi.deleteRule).mockRejectedValue(new Error('Forbidden'))

      const store = useTagStore()
      await store.deleteRule('r1')

      expect(store.error).toBe('Forbidden')
    })
  })

  describe('addPattern', () => {
    it('appends pattern to activeRule when matching', async () => {
      const newPattern: TagRulePattern = { id: 'p2', pattern: 'firefox*', display_name: 'Firefox', category: 'browser', source: 'manual', added_at: '2025-01-01T00:00:00Z', added_by: 'admin' }
      vi.mocked(tagsApi.addPattern).mockResolvedValue(newPattern)

      const store = useTagStore()
      store.activeRule = { ...mockRule, patterns: [mockPattern] }

      const result = await store.addPattern('r1', { pattern: 'firefox*', display_name: 'Firefox', category: 'browser' } as any)

      expect(result).toEqual(newPattern)
      expect(store.activeRule!.patterns).toHaveLength(2)
    })

    it('does not modify activeRule if rule id differs', async () => {
      const newPattern: TagRulePattern = { id: 'p2', pattern: 'firefox*', display_name: 'Firefox', category: 'browser', source: 'manual', added_at: '2025-01-01T00:00:00Z', added_by: 'admin' }
      vi.mocked(tagsApi.addPattern).mockResolvedValue(newPattern)

      const store = useTagStore()
      store.activeRule = { ...mockRule, patterns: [mockPattern] }

      await store.addPattern('different-rule', {} as any)

      expect(store.activeRule!.patterns).toHaveLength(1)
    })

    it('returns null on failure', async () => {
      vi.mocked(tagsApi.addPattern).mockRejectedValue(new Error('Invalid'))

      const store = useTagStore()
      const result = await store.addPattern('r1', {} as any)

      expect(result).toBeNull()
      expect(store.error).toBe('Invalid')
    })
  })

  describe('removePattern', () => {
    it('removes pattern from activeRule', async () => {
      vi.mocked(tagsApi.removePattern).mockResolvedValue(undefined)

      const store = useTagStore()
      store.activeRule = { ...mockRule, patterns: [mockPattern] }

      await store.removePattern('r1', 'p1')

      expect(store.activeRule!.patterns).toEqual([])
    })

    it('does not modify activeRule if rule id differs', async () => {
      vi.mocked(tagsApi.removePattern).mockResolvedValue(undefined)

      const store = useTagStore()
      store.activeRule = { ...mockRule, patterns: [mockPattern] }

      await store.removePattern('other-rule', 'p1')

      expect(store.activeRule!.patterns).toHaveLength(1)
    })
  })

  describe('previewRule', () => {
    it('sets previewResult', async () => {
      const preview = { matched_count: 10, sample_agents: [] }
      vi.mocked(tagsApi.previewRule).mockResolvedValue(preview as any)

      const store = useTagStore()
      await store.previewRule('r1')

      expect(store.previewResult).toEqual(preview)
      expect(store.isPreviewLoading).toBe(false)
    })

    it('sets error on failure', async () => {
      vi.mocked(tagsApi.previewRule).mockRejectedValue(new Error('Timeout'))

      const store = useTagStore()
      await store.previewRule('r1')

      expect(store.error).toBe('Timeout')
    })
  })

  describe('applyRule', () => {
    it('applies rule and refreshes activeRule', async () => {
      const applyResponse = { applied_count: 5 }
      vi.mocked(tagsApi.applyRule).mockResolvedValue(applyResponse as any)
      vi.mocked(tagsApi.getRule).mockResolvedValue({ ...mockRule, tag_name: 'Refreshed' })

      const store = useTagStore()
      store.activeRule = { ...mockRule }

      const result = await store.applyRule('r1')

      expect(result).toEqual(applyResponse)
      expect(store.activeRule!.tag_name).toBe('Refreshed')
      expect(store.isApplying).toBe(false)
    })

    it('does not refresh activeRule if different id', async () => {
      vi.mocked(tagsApi.applyRule).mockResolvedValue({ applied_count: 1 } as any)

      const store = useTagStore()
      store.activeRule = { ...mockRule }

      await store.applyRule('different-rule')

      expect(tagsApi.getRule).not.toHaveBeenCalled()
    })

    it('returns null on failure', async () => {
      vi.mocked(tagsApi.applyRule).mockRejectedValue(new Error('Server error'))

      const store = useTagStore()
      const result = await store.applyRule('r1')

      expect(result).toBeNull()
      expect(store.error).toBe('Server error')
      expect(store.isApplying).toBe(false)
    })
  })
})
