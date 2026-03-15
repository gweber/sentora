/**
 * Simple toast notification composable.
 *
 * Provides a reactive toast message that auto-dismisses after a configurable
 * duration.  Used across views for success/error feedback after user actions.
 *
 * @returns Object with `show()` method, reactive `message`, `type`, and `visible` refs.
 */

import { ref } from 'vue'

export type ToastType = 'success' | 'error' | 'info'

const message = ref('')
const type = ref<ToastType>('success')
const visible = ref(false)

let timer: ReturnType<typeof setTimeout> | null = null

/**
 * Show a toast notification.
 *
 * @param msg - The message to display.
 * @param toastType - Visual style: success (green), error (red), info (blue).
 * @param duration - Auto-dismiss duration in milliseconds (default 3000).
 */
function show(msg: string, toastType: ToastType = 'success', duration = 3000): void {
  if (timer) clearTimeout(timer)
  message.value = msg
  type.value = toastType
  visible.value = true
  timer = setTimeout(() => {
    visible.value = false
  }, duration)
}

/** Dismiss the current toast immediately. */
function dismiss(): void {
  if (timer) clearTimeout(timer)
  visible.value = false
}

export function useToast() {
  return { message, type, visible, show, dismiss }
}
