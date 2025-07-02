"use client"

import { useEffect, useRef, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"

interface CameraStreamProps {
  cameraId: string
  title: string
  width?: number
  height?: number
}

export function CameraStream({ cameraId, title, width = 640, height = 480 }: CameraStreamProps) {
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [streamInfo, setStreamInfo] = useState<any>(null)
  const streamRef = useRef<HTMLImageElement>(null)

  const numericId = parseInt(cameraId, 10);
  if (isNaN(numericId)) {
    console.warn(`CameraStream: cameraId '${cameraId}' is not a valid number.`);
    return <div className="text-red-500">Invalid camera ID</div>;
  }
  
  // Get stream information from our backend
  const streamUrl = `http://localhost:8001/stream/${numericId}`;
  // Use the exact URL pattern that works in MotionEye
  const pictureUrl = `http://localhost:8765/picture/${numericId}/current/?_=${Date.now()}`;

  useEffect(() => {
    // Fetch stream information
    fetch(streamUrl)
      .then(response => response.json())
      .then(data => {
        setStreamInfo(data);
        setIsLoading(false);
      })
      .catch(err => {
        console.error('Error fetching stream info:', err);
        setError('Failed to get camera stream information');
        setIsLoading(false);
      });
  }, [streamUrl]);

  const openMotionEye = () => {
    window.open('http://localhost:8765', '_blank');
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {streamInfo && (
          <div className="text-sm text-muted-foreground">
            MotionEye: {streamInfo.motioneye_url}
          </div>
        )}
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
                <li>Camera is not configured in MotionEye</li>
                <li>RTSP URL is incorrect or camera is offline</li>
                <li>MotionEye needs to be restarted</li>
              </ul>
            </div>
            <div className="flex space-x-2">
              <Button variant="outline" onClick={openMotionEye}>
                Open MotionEye
              </Button>
              <Button variant="outline" onClick={() => window.location.reload()}>
                Retry
              </Button>
            </div>
          </div>
        )}
        <img
          ref={streamRef}
          src={pictureUrl}
          alt={`Camera ${title} stream`}
          style={{ width, height, display: isLoading || error ? 'none' : 'block' }}
          onLoad={() => {
            setIsLoading(false)
            setError(null)
          }}
          onError={() => {
            setIsLoading(false)
            setError('Failed to load camera stream from MotionEye')
          }}
          className="rounded-lg object-cover"
        />
        {streamInfo && !error && (
          <div className="mt-2 text-xs text-muted-foreground">
            <div>RTSP: {streamInfo.rtsp_url}</div>
            <div>Stream: {streamInfo.stream_url}</div>
            <div className="mt-2">
              <Button 
                variant="outline" 
                size="sm" 
                onClick={openMotionEye}
                className="text-xs"
              >
                Configure in MotionEye
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
} 