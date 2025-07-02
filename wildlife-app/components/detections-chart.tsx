"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts"
import { getSpeciesCounts } from "@/lib/api"

export function DetectionsChart() {
  const [range, setRange] = useState<'week' | 'month' | 'all'>('week')
  const [chartData, setChartData] = useState<Array<{species: string, count: number}>>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const fetchSpeciesCounts = async () => {
      setLoading(true)
      try {
        const data = await getSpeciesCounts(range)
        setChartData(data)
      } catch (error) {
        console.error('Error fetching species counts:', error)
        setChartData([])
      } finally {
        setLoading(false)
      }
    }

    fetchSpeciesCounts()
  }, [range])

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