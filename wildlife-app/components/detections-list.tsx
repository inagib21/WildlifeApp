"use client"

import { useEffect, useState } from "react"
import { DetectionCard } from "@/components/detection-card"
import { getDetections, getDetectionsCount } from "@/lib/api"
import { Detection } from "@/types/api"
import { useDetectionsRealtime } from "@/hooks/use-realtime"
import { Badge } from "@/components/ui/badge"
import { AlertCircle, Wifi, WifiOff } from "lucide-react"

export function DetectionsList() {
  const [detections, setDetections] = useState<Detection[]>([])
  const [totalCount, setTotalCount] = useState<number>(0)
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)

  // Real-time connection for new detections
  const { isConnected, error } = useDetectionsRealtime((newDetection) => {
    // Add new detection to the top of the list
    setDetections(prev => [newDetection, ...prev.slice(0, 49)]) // Keep max 50 detections
    setTotalCount(prev => prev + 1) // Increment total count
    setLastUpdate(new Date())
  })

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [data, count] = await Promise.all([
          getDetections(undefined, 50),
          getDetectionsCount()
        ])
        setDetections(data)
        setTotalCount(count)
        setLastUpdate(new Date())
      } catch (error) {
        console.error('Error fetching detections:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading detections...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
        <h1 className="text-3xl font-bold">Recent Detections</h1>
          <div className="flex items-center gap-2">
            {isConnected ? (
              <Badge variant="default" className="bg-green-500">
                <Wifi className="w-3 h-3 mr-1" />
                Live
              </Badge>
            ) : (
              <Badge variant="destructive">
                <WifiOff className="w-3 h-3 mr-1" />
                Offline
              </Badge>
            )}
            {error && (
              <Badge variant="destructive">
                <AlertCircle className="w-3 h-3 mr-1" />
                Error
              </Badge>
            )}
          </div>
        </div>
        <div className="text-sm text-muted-foreground">
          {totalCount} total detections (showing {detections.length} most recent)
          {lastUpdate && (
            <div className="text-xs">
              Last update: {lastUpdate.toLocaleTimeString()}
            </div>
          )}
        </div>
      </div>
      
      {detections.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-muted-foreground mb-4">
            <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium">No detections yet</p>
            <p className="text-sm">Detections will appear here when motion is detected and processed.</p>
          </div>
        </div>
      ) : (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {detections.map((detection) => (
          <DetectionCard
            key={detection.id}
            id={detection.id}
            timestamp={detection.timestamp}
            species={detection.species}
            confidence={detection.confidence}
            imageUrl={detection.media_url || detection.image_path}
            cameraName={detection.camera_name || "Unknown Camera"}
          />
        ))}
      </div>
      )}
    </div>
  )
} 