/**
 * Pagination composable.
 *
 * Tracks current page, page size, and total records. Provides computed
 * values for total pages and navigation controls.
 */

import { computed, ref } from 'vue'

/**
 * Manage pagination state.
 *
 * @param defaultLimit - Initial page size.
 * @returns Reactive pagination state and navigation helpers.
 */
export function usePagination(defaultLimit = 50) {
  const page = ref(1)
  const limit = ref(defaultLimit)
  const total = ref(0)

  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / limit.value)))
  const hasNextPage = computed(() => page.value < totalPages.value)
  const hasPrevPage = computed(() => page.value > 1)

  function nextPage(): void {
    if (hasNextPage.value) page.value++
  }

  function prevPage(): void {
    if (hasPrevPage.value) page.value--
  }

  function goToPage(n: number): void {
    page.value = Math.max(1, Math.min(n, totalPages.value))
  }

  function reset(): void {
    page.value = 1
  }

  return {
    page,
    limit,
    total,
    totalPages,
    hasNextPage,
    hasPrevPage,
    nextPage,
    prevPage,
    goToPage,
    reset,
  }
}
