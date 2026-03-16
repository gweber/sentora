/**
 * Composable for guarding async operations against double-submission.
 *
 * Returns an `execute` wrapper that prevents concurrent invocations and
 * a reactive `isLoading` flag for disabling UI controls during the action.
 *
 * @returns Object with `execute` method and reactive `isLoading` ref.
 */

import { ref } from 'vue'

/**
 * Create a double-submit guard for async actions.
 *
 * @example
 * ```ts
 * const { execute, isLoading } = useAsyncAction()
 * async function handleSave() {
 *   await execute(async () => {
 *     await api.save(payload)
 *   })
 * }
 * ```
 */
export function useAsyncAction() {
  const isLoading = ref(false)

  /**
   * Execute an async function with double-submit protection.
   * Subsequent calls while the previous is in-flight are silently ignored.
   *
   * @param fn - The async function to execute.
   */
  async function execute(fn: () => Promise<void>): Promise<void> {
    if (isLoading.value) return
    isLoading.value = true
    try {
      await fn()
    } finally {
      isLoading.value = false
    }
  }

  return { execute, isLoading }
}
