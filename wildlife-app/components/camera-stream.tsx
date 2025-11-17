"use client"

import { useEffect, useRef, useState } from "react"
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
    <div className="w-full h-full flex items-center justify-center relative">
      {isLoading && (
        <Skeleton className="w-full h-full" />
      )}
      {error && (
        <div className="flex flex-col items-center justify-center space-y-2 p-4" style={{ width, height }}>
          <p className="text-destructive text-center text-sm">
            {error}
          </p>
          <Button 
            variant="outline" 
            size="sm"
            onClick={openMotionEye}
            className="text-xs"
          >
            Open MotionEye
          </Button>
        </div>
      )}
      <img
        ref={streamRef}
        src={pictureUrl}
        alt={`Camera ${title} stream`}
        style={{ 
          width: '100%', 
          height: '100%', 
          display: isLoading || error ? 'none' : 'block',
          objectFit: 'cover'
        }}
        onLoad={() => {
          setIsLoading(false)
          setError(null)
        }}
        onError={() => {
          setIsLoading(false)
          setError('Failed to load camera stream')
        }}
        className="rounded-lg"
      />
    </div>
  )
} 