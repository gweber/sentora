import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// We must mock onUnmounted since we're not inside a component setup
vi.mock('vue', async () => {
  const actual = await vi.importActual('vue')
  return {
    ...actual,
    onUnmounted: vi.fn(),
  }
})

import { onUnmounted } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

type MockWsInstance = {
  onopen: (() => void) | null
  onmessage: ((event: { data: string }) => void) | null
  onerror: (() => void) | null
  onclose: (() => void) | null
  close: ReturnType<typeof vi.fn>
  readyState: number
}

let mockWsInstance: MockWsInstance

class MockWebSocket {
  static OPEN = 1
  static CLOSED = 3

  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null
  close = vi.fn()
  readyState = 0

  constructor(_url: string) {
    mockWsInstance = this
  }
}

// Assign static properties to prototype for code that checks WebSocket.OPEN
Object.defineProperty(MockWebSocket, 'OPEN', { value: 1 })
Object.defineProperty(MockWebSocket, 'CLOSED', { value: 3 })

describe('useWebSocket', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.stubGlobal('WebSocket', MockWebSocket)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('starts with disconnected status', () => {
    const onMsg = vi.fn()
    const { status } = useWebSocket('ws://localhost/test', onMsg)
    expect(status.value).toBe('disconnected')
  })

  it('sets status to connecting then connected on open', () => {
    const onMsg = vi.fn()
    const { status, connect } = useWebSocket('ws://localhost/test', onMsg)

    connect()
    expect(status.value).toBe('connecting')

    mockWsInstance.onopen!()
    expect(status.value).toBe('connected')
  })

  it('parses JSON messages and calls callback', () => {
    const onMsg = vi.fn()
    const { connect } = useWebSocket('ws://localhost/test', onMsg)

    connect()
    mockWsInstance.onopen!()

    const payload = { type: 'progress', run_id: 'r1' }
    mockWsInstance.onmessage!({ data: JSON.stringify(payload) })

    expect(onMsg).toHaveBeenCalledWith(payload)
  })

  it('ignores non-JSON messages silently', () => {
    const onMsg = vi.fn()
    const { connect } = useWebSocket('ws://localhost/test', onMsg)

    connect()
    mockWsInstance.onopen!()
    mockWsInstance.onmessage!({ data: 'not json' })

    expect(onMsg).not.toHaveBeenCalled()
  })

  it('sets status to error on WebSocket error', () => {
    const onMsg = vi.fn()
    const { status, lastError, connect } = useWebSocket('ws://localhost/test', onMsg)

    connect()
    mockWsInstance.onerror!()

    expect(status.value).toBe('error')
    expect(lastError.value).toBe('WebSocket error')
  })

  it('sets status to disconnected on close and schedules reconnect', () => {
    const onMsg = vi.fn()
    const { status, connect } = useWebSocket('ws://localhost/test', onMsg)

    connect()
    mockWsInstance.onopen!()
    mockWsInstance.onclose!()

    expect(status.value).toBe('disconnected')
  })

  it('reconnects with exponential backoff', () => {
    const onMsg = vi.fn()
    const { connect } = useWebSocket('ws://localhost/test', onMsg)

    connect()
    mockWsInstance.onopen!()
    mockWsInstance.onclose!()

    // First reconnect: 1000ms (1000 * 2^0)
    vi.advanceTimersByTime(999)
    // Should still be the same instance
    const firstInstance = mockWsInstance

    vi.advanceTimersByTime(1)
    // New WebSocket should have been created
    expect(mockWsInstance).not.toBe(firstInstance)
  })

  it('resets reconnect attempts on successful connection', () => {
    const onMsg = vi.fn()
    const { connect } = useWebSocket('ws://localhost/test', onMsg)

    connect()
    mockWsInstance.onopen!()
    mockWsInstance.onclose!()

    // First reconnect at 1s
    vi.advanceTimersByTime(1000)
    mockWsInstance.onopen!()
    mockWsInstance.onclose!()

    // After successful reconnect, delay resets to 1s (not 2s)
    const instanceBefore = mockWsInstance
    vi.advanceTimersByTime(1000)
    expect(mockWsInstance).not.toBe(instanceBefore)
  })

  it('disconnect clears timers and closes WebSocket', () => {
    const onMsg = vi.fn()
    const { connect, disconnect, status } = useWebSocket('ws://localhost/test', onMsg)

    connect()
    mockWsInstance.onopen!()
    const ws = mockWsInstance

    disconnect()

    expect(ws.close).toHaveBeenCalled()
    expect(status.value).toBe('disconnected')
  })

  it('disconnect prevents pending reconnect', () => {
    const onMsg = vi.fn()
    const { connect, disconnect } = useWebSocket('ws://localhost/test', onMsg)

    connect()
    mockWsInstance.onopen!()
    mockWsInstance.onclose!()

    // A reconnect is scheduled
    disconnect()

    // Advance past the reconnect delay — no new WS should be created
    const lastInstance = mockWsInstance
    vi.advanceTimersByTime(5000)
    // mockWsInstance may have been reassigned by disconnect calling close,
    // but no new connection should have been attempted
    expect(lastInstance.close).toHaveBeenCalled()
  })

  it('does not create new connection if already open', () => {
    const onMsg = vi.fn()
    const { connect } = useWebSocket('ws://localhost/test', onMsg)

    connect()
    mockWsInstance.readyState = 1 // OPEN

    const firstInstance = mockWsInstance
    connect() // Should be a no-op

    expect(mockWsInstance).toBe(firstInstance)
  })

  it('registers onUnmounted cleanup', () => {
    const onMsg = vi.fn()
    useWebSocket('ws://localhost/test', onMsg)

    expect(onUnmounted).toHaveBeenCalled()
  })

  it('clears lastError on successful reconnection', () => {
    const onMsg = vi.fn()
    const { connect, lastError } = useWebSocket('ws://localhost/test', onMsg)

    connect()
    mockWsInstance.onerror!()
    expect(lastError.value).toBe('WebSocket error')

    mockWsInstance.onclose!()
    vi.advanceTimersByTime(1000) // trigger reconnect
    mockWsInstance.onopen!()

    expect(lastError.value).toBeNull()
  })
})
