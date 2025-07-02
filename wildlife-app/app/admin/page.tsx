'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { RefreshCw, Play, AlertCircle, CheckCircle } from 'lucide-react'

interface PhotoScanStatus {
  total_photos: number
  processed_photos: number
  unprocessed_photos: number
  last_scan: string
  scanner_active: boolean
}

export default function AdminPage() {
  const [status, setStatus] = useState<PhotoScanStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await fetch('http://localhost:8001/api/photo-scan-status')
      if (!response.ok) throw new Error('Failed to fetch status')
      const data = await response.json()
      setStatus(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const triggerScan = async () => {
    try {
      setScanning(true)
      setError(null)
      const response = await fetch('http://localhost:8001/api/trigger-photo-scan')
      if (!response.ok) throw new Error('Failed to trigger scan')
      await fetchStatus() // Refresh status after scan
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setScanning(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    // Refresh status every 30 seconds
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  const getProgressPercentage = () => {
    if (!status || status.total_photos === 0) return 0
    return Math.round((status.processed_photos / status.total_photos) * 100)
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Photo Scanner Admin</h1>
        <Button onClick={fetchStatus} disabled={loading} variant="outline">
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2 text-red-700">
              <AlertCircle className="w-5 h-5" />
              <span>{error}</span>
            </div>
          </CardContent>
        </Card>
      )}

      {status && (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <CheckCircle className="w-5 h-5 text-green-600" />
                <span>Scanner Status</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span>Status:</span>
                  <Badge variant={status.scanner_active ? "default" : "destructive"}>
                    {status.scanner_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span>Last Scan:</span>
                  <span className="text-sm text-gray-600">{status.last_scan}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Photo Statistics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex justify-between">
                  <span>Total Photos:</span>
                  <span className="font-semibold">{status.total_photos}</span>
                </div>
                <div className="flex justify-between">
                  <span>Processed:</span>
                  <span className="font-semibold text-green-600">{status.processed_photos}</span>
                </div>
                <div className="flex justify-between">
                  <span>Unprocessed:</span>
                  <span className="font-semibold text-orange-600">{status.unprocessed_photos}</span>
                </div>
                
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${getProgressPercentage()}%` }}
                  ></div>
                </div>
                <div className="text-center text-sm text-gray-600">
                  {getProgressPercentage()}% Complete
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Actions</CardTitle>
              <CardDescription>
                Manually trigger photo processing
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button 
                onClick={triggerScan} 
                disabled={scanning || status.unprocessed_photos === 0}
                className="w-full"
              >
                <Play className="w-4 h-4 mr-2" />
                {scanning ? 'Processing...' : 'Process Unprocessed Photos'}
              </Button>
              {status.unprocessed_photos === 0 && (
                <p className="text-sm text-gray-500 mt-2 text-center">
                  No unprocessed photos found
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {!status && !loading && (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center text-gray-500">
              No scanner status available
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
} 