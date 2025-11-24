"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useEffect, useState } from "react"
import { useSystemRealtime } from "@/hooks/use-realtime"
import { Badge } from "@/components/ui/badge"
import { Wifi, WifiOff, AlertCircle } from "lucide-react"
import { getSystemHealth } from "@/lib/api"

interface SystemHealth {
  system: {
    cpu_percent: number
    memory_percent: number
    disk_percent: number
    disk_total_gb?: number
    disk_used_gb?: number
    disk_free_gb?: number
    disk_alert?: boolean
    media_disk_info?: {
      motioneye_media_gb: number
      archived_photos_gb: number
      total_media_gb: number
    }
    timestamp: string
  }
  motioneye: {
    status: string
    cameras_count: number
  }
  speciesnet: {
    status: string
  }
  status: string
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"

export function SystemHealth() {
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)
  const [loading, setLoading] = useState(true)

  // Real-time system updates
  const { isConnected, error: connectionError } = useSystemRealtime((systemData) => {
    setHealth(systemData)
    setLastUpdate(new Date())
    setError(null)
    setLoading(false)
  })

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        setLoading(true)
        setError(null)
        
        const data = await getSystemHealth()
        
        // Map the API response to the expected SystemHealth interface
        const mappedHealth: SystemHealth = {
          system: data.system || {
            cpu_percent: 0,
            memory_percent: 0,
            disk_percent: 0,
            disk_total_gb: 0,
            disk_used_gb: 0,
            disk_free_gb: 0,
            disk_alert: false,
            media_disk_info: {
              motioneye_media_gb: 0,
              archived_photos_gb: 0,
              total_media_gb: 0
            },
            timestamp: new Date().toISOString()
          },
          motioneye: {
            status: data.motioneye_status || 'unknown',
            cameras_count: data.cameras || 0
          },
          speciesnet: {
            status: data.speciesnet_status || 'unknown'
          },
          status: data.status || 'unknown'
        }
        
        setHealth(mappedHealth)
        setLastUpdate(new Date())
      } catch (err) {
        console.error('Error fetching system health:', err)
        setError(err instanceof Error ? err.message : 'Failed to fetch system health')
        // Set default health data to prevent complete failure
        setHealth({
          system: {
            cpu_percent: 0,
            memory_percent: 0,
            disk_percent: 0,
            disk_total_gb: 0,
            disk_used_gb: 0,
            disk_free_gb: 0,
            disk_alert: false,
            media_disk_info: {
              motioneye_media_gb: 0,
              archived_photos_gb: 0,
              total_media_gb: 0
            },
            timestamp: new Date().toISOString()
          },
          motioneye: {
            status: 'unknown',
            cameras_count: 0
          },
          speciesnet: {
            status: 'unknown'
          },
          status: 'error'
        })
      } finally {
        setLoading(false)
      }
    }

    fetchHealth()
  }, [])

  if (loading && !health) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>System Health</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
            <span className="ml-2">Loading system health...</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error && !health) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            System Health
            <Badge variant="destructive">
              <AlertCircle className="w-3 h-3 mr-1" />
              Error
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-red-500">Error: {error}</p>
          <p className="text-sm text-muted-foreground mt-2">
            Make sure the backend server is running at {API_BASE_URL}
          </p>
        </CardContent>
      </Card>
    )
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'text-green-600'
      case 'error':
        return 'text-red-600'
      default:
        return 'text-yellow-600'
    }
  }

  return (
    <div className="space-y-4">
      {/* Real-time status indicator */}
      <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
        <div className="flex items-center gap-2">
          {isConnected ? (
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
          {connectionError && (
            <Badge variant="destructive">
              <AlertCircle className="w-3 h-3 mr-1" />
              Connection Error
            </Badge>
          )}
        </div>
        {lastUpdate && (
          <div className="text-sm text-muted-foreground">
            Last update: {lastUpdate.toLocaleTimeString()}
          </div>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Service Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="font-medium">MotionEye</p>
                <p className={`text-sm ${getStatusColor(health?.motioneye?.status || 'unknown')}`}>
                  {health?.motioneye?.status === "running" ? "Running" : health?.motioneye?.status || "Unknown"}
                </p>
              </div>
              <div className="flex items-center justify-between">
                <p className="font-medium">SpeciesNet</p>
                <p className={`text-sm ${getStatusColor(health?.speciesnet?.status || 'unknown')}`}>
                  {health?.speciesnet?.status === "running" ? "Running" : health?.speciesnet?.status || "Unknown"}
                </p>
              </div>
              <div className="flex items-center justify-between">
                <p className="font-medium">Cameras</p>
                <p className="text-sm">{health?.motioneye?.cameras_count || 0} cameras</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Resource Usage</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="font-medium">CPU Usage</p>
                <p className="text-sm">{health?.system?.cpu_percent?.toFixed(1) || 'N/A'}%</p>
              </div>
              <div className="flex items-center justify-between">
                <p className="font-medium">Memory Usage</p>
                <p className="text-sm">{health?.system?.memory_percent?.toFixed(1) || 'N/A'}%</p>
              </div>
              <div className="flex items-center justify-between">
                <p className="font-medium">Disk Usage</p>
                <div className="flex items-center gap-2">
                  <p className={`text-sm ${health?.system?.disk_alert ? 'text-red-600 font-bold' : ''}`}>
                    {health?.system?.disk_percent?.toFixed(1) || 'N/A'}%
                  </p>
                  {health?.system?.disk_alert && (
                    <AlertCircle className="w-4 h-4 text-red-600" />
                  )}
                </div>
              </div>
              {health?.system?.disk_total_gb && (
                <>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <p>Total: {health.system.disk_total_gb.toFixed(1)} GB</p>
                    <p>Free: {health.system.disk_free_gb?.toFixed(1) || 'N/A'} GB</p>
                  </div>
                  {health?.system?.media_disk_info && health.system.media_disk_info.total_media_gb > 0 && (
                    <div className="mt-2 pt-2 border-t text-xs">
                      <p className="font-medium mb-1">Media Storage:</p>
                      <p className="text-muted-foreground">
                        MotionEye: {health.system.media_disk_info.motioneye_media_gb.toFixed(2)} GB
                      </p>
                      <p className="text-muted-foreground">
                        Archived: {health.system.media_disk_info.archived_photos_gb.toFixed(2)} GB
                      </p>
                      <p className="text-muted-foreground font-medium">
                        Total Media: {health.system.media_disk_info.total_media_gb.toFixed(2)} GB
                      </p>
                    </div>
                  )}
                </>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Access Links</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="font-medium">MotionEye</p>
                <p className="text-sm text-blue-600 hover:underline">
                  <a href="http://localhost:8765" target="_blank" rel="noopener noreferrer">
                    Open MotionEye
                  </a>
                </p>
              </div>
              <div className="flex items-center justify-between">
                <p className="font-medium">Backend API</p>
                <p className="text-sm text-blue-600 hover:underline">
                  <a href={API_BASE_URL} target="_blank" rel="noopener noreferrer">
                    API Docs
                  </a>
                </p>
              </div>
              <div className="flex items-center justify-between">
                <p className="font-medium">System Events</p>
                <p className="text-sm text-blue-600 hover:underline">
                  <a href={`${API_BASE_URL}/events/system`} target="_blank" rel="noopener noreferrer">
                    SSE Stream
                  </a>
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
} 