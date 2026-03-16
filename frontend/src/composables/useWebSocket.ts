/**
 * WebSocket composable with automatic reconnection.
 *
 * Provides a reactive WebSocket connection with exponential backoff reconnection.
 * Used for live sync progress and classification updates.
 */

import { ref, onScopeDispose } from 'vue'

export type WsStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

/**
 * Create a managed WebSocket connection with auto-reconnect.
 *
 * @param url - WebSocket URL (ws:// or wss://).
 * @param onMessage - Callback invoked for each received message.
 * @returns Reactive status, connect/disconnect controls, and last error.
 */
export function useWebSocket(url: string, onMessage: (data: unknown) => void) {
  const status = ref<WsStatus>('disconnected')
  const lastError = ref<string | null>(null)

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempts = 0
  let intentionalClose = false
  const MAX_RECONNECT_DELAY = 30_000

  function connect(): void {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return
    intentionalClose = false
    status.value = 'connecting'
    // Pass JWT via the Sec-WebSocket-Protocol header to avoid leaking
    // the token in query strings (server logs, browser history, proxies).
    // The backend reads it from the first subprotocol value.
    const token = localStorage.getItem('sentora_token')
    const protocols = token ? [`bearer.${token}`] : undefined
    ws = new WebSocket(url, protocols)

    ws.onopen = () => {
      status.value = 'connected'
      lastError.value = null
      reconnectAttempts = 0
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string)
        onMessage(data)
      } catch {
        // Non-JSON ping frames — ignore
      }
    }

    ws.onerror = () => {
      status.value = 'error'
      lastError.value = 'WebSocket error'
    }

    ws.onclose = (event) => {
      status.value = 'disconnected'
      // Normal closure — don't reconnect
      if (event?.code === 1000) return
      // Don't reconnect on auth rejection — the token needs refreshing first
      if (event?.code === 4001) {
        lastError.value = 'Authentication failed'
        return
      }
      scheduleReconnect()
    }
  }

  function disconnect(): void {
    intentionalClose = true
    const socket = ws
    ws = null
    status.value = 'disconnected'
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    socket?.close()
  }

  function scheduleReconnect(): void {
    if (intentionalClose) return
    const delay = Math.min(1000 * 2 ** reconnectAttempts, MAX_RECONNECT_DELAY)
    reconnectAttempts++
    reconnectTimer = setTimeout(connect, delay)
  }

  onScopeDispose(disconnect)

  return { status, lastError, connect, disconnect }
}
