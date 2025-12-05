"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts"
import { getSpeciesCounts } from "@/lib/api"

export function DetectionsChart() {
  const [range, setRange] = useState<'week' | 'month' | 'all'>('week')
  const [chartData, setChartData] = useState<Array<{species: string, count: number}>>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchSpeciesCounts = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await getSpeciesCounts(range)
        setChartData(data)
      } catch (error: any) {
        console.error('Error fetching species counts:', error)
        setChartData([])
        
        // Set error message for connection errors
        if (error?.code === 'ECONNREFUSED' || error?.message?.includes('Network Error') || error?.message?.includes('ERR_NETWORK')) {
          setError('Backend server is not responding. Please ensure the backend is running on port 8001.')
        } else if (error?.code === 'ECONNABORTED' || error?.message?.includes('timeout')) {
          setError('Request timed out. The backend may be slow or unresponsive.')
        } else {
          setError('Failed to load species counts. Please try again.')
        }
      } finally {
        setLoading(false)
      }
    }

    fetchSpeciesCounts()
  }, [range])

  // If error, show error message with retry button
  if (error && !loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Species Detections</CardTitle>
          <CardDescription>Most common species detected by cameras</CardDescription>
          <div className="mt-2 flex gap-2">
            <button onClick={() => setRange('week')} className={`px-2 py-1 rounded ${range === 'week' ? 'bg-blue-500 text-white' : 'bg-muted'}`}>Past Week</button>
            <button onClick={() => setRange('month')} className={`px-2 py-1 rounded ${range === 'month' ? 'bg-blue-500 text-white' : 'bg-muted'}`}>Past Month</button>
            <button onClick={() => setRange('all')} className={`px-2 py-1 rounded ${range === 'all' ? 'bg-blue-500 text-white' : 'bg-muted'}`}>All Time</button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center h-64 gap-3">
            <p className="text-red-500 font-medium">⚠️ Backend Server Not Available</p>
            <p className="text-sm text-muted-foreground text-center max-w-md">{error}</p>
            <button 
              onClick={() => {
                setError(null)
                setLoading(true)
                const fetchSpeciesCounts = async () => {
                  try {
                    const data = await getSpeciesCounts(range)
                    setChartData(data)
                    setError(null)
                  } catch (err: any) {
                    setChartData([])
                    if (err?.code === 'ECONNREFUSED' || err?.message?.includes('Network Error')) {
                      setError('Backend server is not responding. Please ensure the backend is running on port 8001.')
                    } else {
                      setError('Failed to load species counts. Please try again.')
                    }
                  } finally {
                    setLoading(false)
                  }
                }
                fetchSpeciesCounts()
              }}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
            >
              Retry Connection
            </button>
            <p className="text-xs text-muted-foreground text-center max-w-md">
              Make sure the backend is running: <code className="bg-muted px-1 rounded">scripts\control.bat</code> → Start All Services
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  // If no detections, show placeholder
  if (chartData.length === 0 && !loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Species Detections</CardTitle>
          <CardDescription>Most common species detected by cameras</CardDescription>
          <div className="mt-2 flex gap-2">
            <button onClick={() => setRange('week')} className={`px-2 py-1 rounded ${range === 'week' ? 'bg-blue-500 text-white' : 'bg-muted'}`}>Past Week</button>
            <button onClick={() => setRange('month')} className={`px-2 py-1 rounded ${range === 'month' ? 'bg-blue-500 text-white' : 'bg-muted'}`}>Past Month</button>
            <button onClick={() => setRange('all')} className={`px-2 py-1 rounded ${range === 'all' ? 'bg-blue-500 text-white' : 'bg-muted'}`}>All Time</button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-64">
            <p className="text-muted-foreground">No detections available</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Species Detections</CardTitle>
        <CardDescription>Most common species detected by cameras</CardDescription>
        <div className="mt-2 flex gap-2">
          <button onClick={() => setRange('week')} className={`px-2 py-1 rounded ${range === 'week' ? 'bg-blue-500 text-white' : 'bg-muted'}`}>Past Week</button>
          <button onClick={() => setRange('month')} className={`px-2 py-1 rounded ${range === 'month' ? 'bg-blue-500 text-white' : 'bg-muted'}`}>Past Month</button>
          <button onClick={() => setRange('all')} className={`px-2 py-1 rounded ${range === 'all' ? 'bg-blue-500 text-white' : 'bg-muted'}`}>All Time</button>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="species" 
                  angle={-45}
                  textAnchor="end"
                  height={80}
                  interval={0}
                  tick={{ fontSize: 12 }}
                />
                <YAxis />
                <Tooltip 
                  formatter={(value: number) => [`${value} detections`, 'Count']}
                  labelFormatter={(label: string) => `Species: ${label}`}
                />
                <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-4 text-sm text-muted-foreground">
              Showing top {chartData.length} species for {range === 'week' ? 'past week' : range === 'month' ? 'past month' : 'all time'}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
} 