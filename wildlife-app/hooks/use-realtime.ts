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
        setIsConnected(false)
        setError('Connection error')
        onError?.(event)

        // Attempt to reconnect
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, reconnectInterval)
        }
      }

      eventSource.onclose = () => {
        setIsConnected(false)
        onClose?.()
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
      }
    },
    onError: (error) => {
      console.error('Detections SSE error:', error)
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
      if (data.type === 'system') {
        onSystemUpdate?.(data.data)
      }
    },
    onError: (error) => {
      console.error('System SSE error:', error)
    }
  })
} 