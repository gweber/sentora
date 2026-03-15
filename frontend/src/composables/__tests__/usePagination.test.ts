import { describe, it, expect } from 'vitest'
import { usePagination } from '@/composables/usePagination'

describe('usePagination', () => {
  describe('initial state', () => {
    it('starts at page 1 with default limit of 50', () => {
      const { page, limit, total } = usePagination()
      expect(page.value).toBe(1)
      expect(limit.value).toBe(50)
      expect(total.value).toBe(0)
    })

    it('accepts custom default limit', () => {
      const { limit } = usePagination(25)
      expect(limit.value).toBe(25)
    })
  })

  describe('totalPages', () => {
    it('computes correctly for exact division', () => {
      const { totalPages, total, limit } = usePagination(10)
      total.value = 30
      expect(totalPages.value).toBe(3)
    })

    it('rounds up for partial pages', () => {
      const { totalPages, total, limit } = usePagination(10)
      total.value = 31
      expect(totalPages.value).toBe(4)
    })

    it('returns 1 when total is 0', () => {
      const { totalPages } = usePagination()
      expect(totalPages.value).toBe(1)
    })

    it('returns 1 when total equals limit', () => {
      const { totalPages, total } = usePagination(10)
      total.value = 10
      expect(totalPages.value).toBe(1)
    })
  })

  describe('hasNextPage / hasPrevPage', () => {
    it('hasNextPage is false on single page', () => {
      const { hasNextPage, total } = usePagination(10)
      total.value = 5
      expect(hasNextPage.value).toBe(false)
    })

    it('hasNextPage is true when more pages exist', () => {
      const { hasNextPage, total } = usePagination(10)
      total.value = 25
      expect(hasNextPage.value).toBe(true)
    })

    it('hasPrevPage is false on page 1', () => {
      const { hasPrevPage } = usePagination()
      expect(hasPrevPage.value).toBe(false)
    })

    it('hasPrevPage is true on page > 1', () => {
      const { hasPrevPage, page, total } = usePagination(10)
      total.value = 50
      page.value = 2
      expect(hasPrevPage.value).toBe(true)
    })
  })

  describe('nextPage', () => {
    it('increments page when hasNextPage', () => {
      const { page, total, nextPage } = usePagination(10)
      total.value = 25
      nextPage()
      expect(page.value).toBe(2)
    })

    it('does not exceed totalPages', () => {
      const { page, total, nextPage } = usePagination(10)
      total.value = 15
      page.value = 2 // last page
      nextPage()
      expect(page.value).toBe(2)
    })
  })

  describe('prevPage', () => {
    it('decrements page when hasPrevPage', () => {
      const { page, total, prevPage } = usePagination(10)
      total.value = 50
      page.value = 3
      prevPage()
      expect(page.value).toBe(2)
    })

    it('does not go below 1', () => {
      const { page, prevPage } = usePagination()
      prevPage()
      expect(page.value).toBe(1)
    })
  })

  describe('goToPage', () => {
    it('sets page to the specified value', () => {
      const { page, total, goToPage } = usePagination(10)
      total.value = 50
      goToPage(3)
      expect(page.value).toBe(3)
    })

    it('clamps to 1 when given value below 1', () => {
      const { page, goToPage } = usePagination()
      goToPage(0)
      expect(page.value).toBe(1)

      goToPage(-5)
      expect(page.value).toBe(1)
    })

    it('clamps to totalPages when given value above max', () => {
      const { page, total, goToPage } = usePagination(10)
      total.value = 25
      goToPage(100)
      expect(page.value).toBe(3)
    })
  })

  describe('reset', () => {
    it('resets page to 1', () => {
      const { page, total, reset } = usePagination(10)
      total.value = 50
      page.value = 4
      reset()
      expect(page.value).toBe(1)
    })
  })
})
