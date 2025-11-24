"use client"

import { useEffect, useState } from "react"
import { ChartAreaInteractive } from "@/components/chart-area-interactive"
import { DataTable } from "@/components/data-table"
import { SectionCards } from "@/components/section-cards"
import { SystemHealth } from "@/components/system-health"
import { DetectionsChart } from "@/components/detections-chart"
import { DetectionsTimelineChart } from "@/components/detections-timeline-chart"
import { getCameras, getDetections, getDetectionsCount, getUniqueSpeciesCount, getSystemHealth, getDetectionsChunked, getDetectionsTimeseries, getTopSpecies, getUniqueSpeciesCountFast } from "@/lib/api"
import { Camera, Detection } from "@/types/api"
import { useDetectionsRealtime, useSystemRealtime } from "@/hooks/use-realtime"
import { Badge } from "@/components/ui/badge"
import { Wifi, WifiOff, AlertCircle } from "lucide-react"

// Placeholder data for when backend is not available
const placeholderCameras: Camera[] = [
  {
    id: 1,
    name: "Camera 1",
    url: "rtsp://example.com/stream1",
    is_active: true,
    created_at: new Date().toISOString()
  },
  {
    id: 2,
    name: "Camera 2",
    url: "rtsp://example.com/stream2",
    is_active: true,
    created_at: new Date().toISOString()
  }
]

const placeholderDetections: Detection[] = [
  {
    id: 1,
    camera_id: 1,
    timestamp: new Date().toISOString(),
    species: "Unknown",
    confidence: 0.0,
    image_path: "",
    media_url: ""
  }
]

export function RealtimeDashboard() {
  // KPI states
  const [cameras, setCameras] = useState<Camera[] | null>(null)
  const [detections, setDetections] = useState<Detection[] | null>(null)
  const [systemHealth, setSystemHealth] = useState<any>(null)
  const [totalDetectionsCount, setTotalDetectionsCount] = useState<number | null>(null)
  const [totalUniqueSpecies, setTotalUniqueSpecies] = useState<number | null>(null)
  const [allDetections, setAllDetections] = useState<Detection[]>([])
  const [error, setError] = useState<Error | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)

  // Real-time connections
  const { isConnected: detectionsConnected, error: detectionsError } = useDetectionsRealtime((newDetection) => {
    // Update detections list
    setDetections(prev => prev ? [newDetection, ...prev.slice(0, 49)] : [newDetection])
    
    // Update KPI counts in real-time
    setTotalDetectionsCount(prev => (prev ?? 0) + 1)
    
    // Update camera detection counts in real-time
    setCameras(prev => {
      if (!prev) return prev
      return prev.map(camera => {
        if (camera.id === newDetection.camera_id) {
          return {
            ...camera,
            detection_count: (camera.detection_count || 0) + 1,
            last_detection: newDetection.timestamp
          }
        }
        return camera
      })
    })
    
    // Update unique species count (simplified - just increment if new species)
    // Note: This is approximate, for exact count we'd need to refetch
    setTotalUniqueSpecies(prev => {
      if (!prev) return 1
      // Check if this is a new species by looking at existing detections
      const existingSpecies = new Set((detections || []).map(d => d.species).filter(Boolean))
      if (!existingSpecies.has(newDetection.species) && newDetection.species && newDetection.species !== 'Unknown') {
        return prev + 1
      }
      return prev
    })
    
    // Update allDetections for charts
    setAllDetections(prev => [newDetection, ...prev].slice(0, 2000))
    
    setLastUpdate(new Date())
  })
  const { isConnected: systemConnected, error: systemError } = useSystemRealtime((systemData) => {
    setSystemHealth(systemData)
    setLastUpdate(new Date())
  })

  // Fetch each KPI independently
  useEffect(() => {
    getCameras().then(setCameras).catch(e => setError(e instanceof Error ? e : new Error(String(e))))
    getDetections({ limit: 50 }).then(setDetections).catch(e => setError(e instanceof Error ? e : new Error(String(e))))
    getSystemHealth().then(setSystemHealth).catch(e => setError(e instanceof Error ? e : new Error(String(e))))
    getDetectionsCount().then(setTotalDetectionsCount).catch(e => setError(e instanceof Error ? e : new Error(String(e))))
    getUniqueSpeciesCountFast(30).then(setTotalUniqueSpecies).catch(e => setError(e instanceof Error ? e : new Error(String(e))))
    // Fetch large dataset in chunks (non-blocking)
    setTimeout(async () => {
      try {
        const allDetectionsData = await getDetectionsChunked(undefined, 2000)
        setAllDetections(allDetectionsData)
      } catch (e) {
        console.error('Error loading large dataset:', e)
      }
    }, 1000)
    setLastUpdate(new Date())
  }, [])

  // Show loading state if all KPIs are still loading
  if (!cameras && !detections && !systemHealth && !totalDetectionsCount && !totalUniqueSpecies) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4 md:space-y-6">
      {/* Real-time status indicator */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 md:p-4 bg-muted rounded-lg">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold">Live Dashboard</h2>
          <div className="flex items-center gap-2">
            {detectionsConnected && systemConnected ? (
              <Badge variant="default" className="bg-green-500">
                <Wifi className="w-3 h-3 mr-1" />
                Live Updates
              </Badge>
            ) : (
              <Badge variant="destructive">
                <WifiOff className="w-3 h-3 mr-1" />
                Offline
              </Badge>
            )}
            {(detectionsError || systemError) && (
              <Badge variant="destructive">
                <AlertCircle className="w-3 h-3 mr-1" />
                Connection Error
              </Badge>
            )}
          </div>
        </div>
        {lastUpdate && (
          <div className="text-sm text-muted-foreground">
            Last update: {lastUpdate.toLocaleTimeString()}
          </div>
        )}
      </div>

      {/* KPI Cards: show loading spinners for each if not ready */}
      <SystemHealth />
      <SectionCards
        cameras={cameras || []}
        detections={detections || []}
        totalDetectionsCount={totalDetectionsCount ?? 0}
        totalUniqueSpecies={totalUniqueSpecies ?? 0}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 md:gap-6">
        <DetectionsChart />
        <DetectionsTimelineChart detections={allDetections} />
      </div>

      <div className="rounded-lg border bg-card p-4 md:p-6">
        <ChartAreaInteractive />
      </div>

      <div className="rounded-lg border bg-card">
        <DataTable data={cameras || []} />
      </div>

      {error && (
        <div className="fixed bottom-4 right-4 bg-yellow-100 border border-yellow-400 text-yellow-700 px-4 py-3 rounded">
          <p>Backend connection failed. Showing placeholder data.</p>
        </div>
      )}
    </div>
  )
} 