"use client"

import { useEffect, useRef, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"

interface ThinginoCameraStreamProps {
  cameraId: string
  title: string
  width?: number
  height?: number
  streamUrl: string
}

export function ThinginoCameraStream({ 
  cameraId, 
  title, 
  width = 640, 
  height = 480, 
  streamUrl 
}: ThinginoCameraStreamProps) {
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [isCapturing, setIsCapturing] = useState(false)
  const [lastCapture, setLastCapture] = useState<string | null>(null)
  const streamRef = useRef<HTMLImageElement>(null)
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null)

  // For MJPEG streams, we need to refresh the image periodically
  const refreshStream = () => {
    if (streamRef.current) {
      const img = streamRef.current
      const currentSrc = img.src
      // Add timestamp to force refresh
      img.src = `${streamUrl}?_=${Date.now()}`
    }
  }

  useEffect(() => {
    // Start periodic refresh for MJPEG stream
    refreshIntervalRef.current = setInterval(refreshStream, 1000) // Refresh every second
    
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current)
      }
    }
  }, [streamUrl])

  const handleImageLoad = () => {
    setIsLoading(false)
    setError(null)
    setIsStreaming(true)
  }

  const handleImageError = () => {
    setIsLoading(false)
    setError('Failed to load camera stream. Check if camera is online and accessible.')
    setIsStreaming(false)
  }

  const retryConnection = () => {
    setIsLoading(true)
    setError(null)
    setIsStreaming(false)
    refreshStream()
  }

  const captureImage = async () => {
    setIsCapturing(true)
    try {
      const response = await fetch(`http://localhost:8001/api/thingino/capture?camera_id=${cameraId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      if (response.ok) {
        const result = await response.json()
        setLastCapture(`Captured: ${result.species} (${(result.confidence * 100).toFixed(1)}%)`)
        console.log('Capture result:', result)
      } else {
        const errorData = await response.json()
        setError(`Capture failed: ${errorData.detail}`)
      }
    } catch (err) {
      setError(`Capture failed: ${err}`)
    } finally {
      setIsCapturing(false)
    }
  }

  return (
    <Card className="w-full">
      <CardHeader className="bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-950/20 dark:to-emerald-950/20">
        <CardTitle className="flex items-center gap-2">
          <span className="text-green-600">📹</span>
          {title}
        </CardTitle>
        <div className="text-sm text-muted-foreground flex items-center gap-2">
          <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
          Thingino MJPEG Stream
        </div>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <Skeleton className="w-full" style={{ width, height }} />
        )}
        {error && (
          <div className="flex flex-col items-center justify-center space-y-4" style={{ width, height }}>
            <p className="text-destructive text-center">
              {error}
            </p>
            <div className="text-sm text-muted-foreground text-center space-y-2">
              <p>Camera stream is not available. This could be because:</p>
              <ul className="list-disc list-inside space-y-1">
                <li>Camera is offline or not accessible</li>
                <li>Network connection issues</li>
                <li>Camera requires authentication</li>
                <li>Camera URL is incorrect</li>
              </ul>
            </div>
            <div className="flex space-x-2">
              <Button variant="outline" onClick={retryConnection}>
                Retry Connection
              </Button>
              <Button variant="outline" onClick={() => window.location.reload()}>
                Refresh Page
              </Button>
            </div>
          </div>
        )}
        <img
          ref={streamRef}
          src={`${streamUrl}?_=${Date.now()}`}
          alt={`${title} stream`}
          style={{ width, height, display: isLoading || error ? 'none' : 'block' }}
          onLoad={handleImageLoad}
          onError={handleImageError}
          className="rounded-lg object-cover"
        />
        {isStreaming && !error && (
          <div className="mt-2 text-xs text-muted-foreground">
            <div>Stream URL: {streamUrl}</div>
            <div className="flex items-center space-x-2 mt-2">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span>Live Stream Active</span>
            </div>
            {lastCapture && (
              <div className="mt-2 p-2 bg-green-50 dark:bg-green-900/20 rounded text-green-700 dark:text-green-300">
                {lastCapture}
              </div>
            )}
            <div className="mt-2 flex space-x-2">
              <Button 
                variant="outline" 
                size="sm" 
                onClick={retryConnection}
                className="text-xs"
              >
                Refresh Stream
              </Button>
              <Button 
                variant="default" 
                size="sm" 
                onClick={captureImage}
                disabled={isCapturing}
                className="text-xs"
              >
                {isCapturing ? 'Capturing...' : 'Capture & Analyze'}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
