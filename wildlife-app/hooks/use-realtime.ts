import { useEffect, useRef, useState } from 'react'

interface RealtimeOptions {
  onMessage?: (data: any) => void
  onError?: (error: Event) => void
  onOpen?: () => void
  onClose?: () => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

export function useRealtime(url: string, options: RealtimeOptions = {}) {
  const {
    onMessage,
    onError,
    onOpen,
    onClose,
    reconnectInterval = 5000,
    maxReconnectAttempts = 5
  } = options

  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const connect = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    try {
      const eventSource = new EventSource(url)
      eventSourceRef.current = eventSource

      eventSource.onopen = () => {
        setIsConnected(true)
        setError(null)
        reconnectAttemptsRef.current = 0
        onOpen?.()
      }

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onMessage?.(data)
        } catch (err) {
          console.error('Error parsing SSE message:', err)
        }
      }

      eventSource.onerror = (event) => {
        const target = event.target as EventSource
        const readyState = target?.readyState
        
        // EventSource.onerror fires in different states:
        // - CONNECTING (0): Initial connection attempt or reconnection attempt
        // - OPEN (1): Connection established (errors here are rare)
        // - CLOSED (2): Connection was closed
        
        if (readyState === EventSource.CLOSED) {
          // Connection was closed - this is a real error
          setIsConnected(false)
          setError('Connection closed')
          
          // Attempt to reconnect
          if (reconnectAttemptsRef.current < maxReconnectAttempts) {
            reconnectAttemptsRef.current++
            reconnectTimeoutRef.current = setTimeout(() => {
              connect()
            }, reconnectInterval)
          }
        } else if (readyState === EventSource.CONNECTING) {
          // Still trying to connect - this is normal during initial connection or reconnection
          // Don't log as error, just wait for connection to establish or fail
          // The connection will either succeed (onopen) or fail and close (then we'll reconnect)
          setIsConnected(false)
          setError(null) // Clear any previous error while connecting
        } else if (readyState === EventSource.OPEN) {
          // Connection is open but error occurred - this is unusual
          // Don't disconnect immediately, let it try to recover
          console.warn('EventSource error while connection is open')
        }
        
        // Only call onError callback for actual errors (not CONNECTING state)
        if (readyState !== EventSource.CONNECTING) {
          onError?.(event)
        }
        
        // Handle connection close
        if (readyState === EventSource.CLOSED) {
          setIsConnected(false)
          onClose?.()
        }
      }
    } catch (err) {
      setError('Failed to create connection')
      console.error('Error creating EventSource:', err)
    }
  }

  const disconnect = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    setIsConnected(false)
  }

  useEffect(() => {
    connect()

    return () => {
      disconnect()
    }
  }, [url])

  return {
    isConnected,
    error,
    connect,
    disconnect
  }
}

// Specialized hook for detections
export function useDetectionsRealtime(onNewDetection?: (detection: any) => void) {
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'
  
  return useRealtime(`${API_URL}/events/detections`, {
    onMessage: (data) => {
      // Handle different event formats from backend
      if (data.type === 'detection') {
        // Format: { type: 'detection', data: detectionObject, timestamp: ... }
        onNewDetection?.(data.data || data.detection || data)
      } else if (data.id && data.species !== undefined) {
        // Direct detection object format
        onNewDetection?.(data)
      } else if (data.type === 'keepalive') {
        // Ignore keepalive messages
        return
      }
    },
    onError: (error) => {
      // EventSource error events don't have much info, log what we can
      const target = error.target as EventSource
      const readyState = target?.readyState
      
      // Only log actual errors (not CONNECTING state which is normal)
      if (readyState === EventSource.CLOSED) {
        console.warn('Detections SSE connection closed, will attempt to reconnect...')
      } else if (readyState === EventSource.OPEN) {
        console.warn('Detections SSE error while connected')
      }
      // Don't log CONNECTING state - it's normal during connection attempts
    },
    reconnectInterval: 3000, // Faster reconnection for detections
    maxReconnectAttempts: 10 // More attempts for critical real-time data
  })
}

// Specialized hook for system updates
export function useSystemRealtime(onSystemUpdate?: (systemData: any) => void) {
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'
  
  return useRealtime(`${API_URL}/events/system`, {
    onMessage: (data) => {
      // Handle different event formats
      if (data.type === 'system' || data.type === 'system_update') {
        onSystemUpdate?.(data.data || data)
      } else if (data.type === 'keepalive') {
        // Ignore keepalive messages
        return
      } else if (data.system || data.motioneye || data.speciesnet) {
        // Direct system health data format
        onSystemUpdate?.(data)
      }
    },
    onError: (error) => {
      // EventSource error events don't have much info, log what we can
      const target = error.target as EventSource
      const readyState = target?.readyState
      
      // Only log actual errors (not CONNECTING state which is normal)
      if (readyState === EventSource.CLOSED) {
        console.warn('System SSE connection closed, will attempt to reconnect...')
      } else if (readyState === EventSource.OPEN) {
        console.warn('System SSE error while connected')
      }
      // Don't log CONNECTING state - it's normal during connection attempts
    },
    reconnectInterval: 5000, // Reconnect every 5 seconds
    maxReconnectAttempts: 10 // More attempts for system updates
  })
} 