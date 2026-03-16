/**
 * Global test setup for Vitest.
 *
 * Provides common mocks (WebSocket, URL.createObjectURL, etc.) that are
 * needed across multiple test files.
 */

import { vi } from 'vitest'

// Mock URL.createObjectURL / revokeObjectURL for blob-download tests
if (typeof URL.createObjectURL === 'undefined') {
  URL.createObjectURL = vi.fn(() => 'blob:mock-url')
}
if (typeof URL.revokeObjectURL === 'undefined') {
  URL.revokeObjectURL = vi.fn()
}
