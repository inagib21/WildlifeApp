'use client'

import React, { useEffect, useState, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { getAuditLogs, AuditLog, AuditLogFilters } from '@/lib/api'
import { toast } from 'sonner'

export function AuditLogs() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState<AuditLogFilters>({
    limit: 100,
    offset: 0
  })
  const [selectedAction, setSelectedAction] = useState<string>('all')
  const [selectedResourceType, setSelectedResourceType] = useState<string>('all')
  const [successOnly, setSuccessOnly] = useState(false)

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true)
      const filterParams: AuditLogFilters = {
        limit: filters.limit || 100,
        offset: filters.offset || 0
      }
      
      if (selectedAction !== 'all') {
        filterParams.action = selectedAction
      }
      if (selectedResourceType !== 'all') {
        filterParams.resource_type = selectedResourceType
      }
      if (successOnly) {
        filterParams.success_only = true
      }
      
      const data = await getAuditLogs(filterParams)
      setLogs(data)
    } catch (error: any) {
      console.error('Error fetching audit logs:', error)
      toast.error(error.message || 'Failed to fetch audit logs')
      setLogs([])
    } finally {
      setLoading(false)
    }
  }, [filters, selectedAction, selectedResourceType, successOnly])

  useEffect(() => {
    fetchLogs()
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchLogs, 30000)
    return () => clearInterval(interval)
  }, [fetchLogs])

  const getActionColor = (action: string) => {
    switch (action.toUpperCase()) {
      case 'CREATE':
        return 'bg-green-500'
      case 'UPDATE':
        return 'bg-blue-500'
      case 'DELETE':
        return 'bg-red-500'
      case 'SYNC':
        return 'bg-purple-500'
      case 'WEBHOOK':
        return 'bg-orange-500'
      case 'CAPTURE':
        return 'bg-cyan-500'
      case 'PROCESS':
        return 'bg-indigo-500'
      case 'TRIGGER':
        return 'bg-yellow-500'
      default:
        return 'bg-gray-500'
    }
  }

  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp)
      return date.toLocaleString()
    } catch {
      return timestamp
    }
  }

  const parseDetails = (details?: string) => {
    if (!details) return null
    try {
      return JSON.parse(details)
    } catch {
      return null
    }
  }

  const uniqueActions = Array.from(new Set(logs.map(log => log.action))).sort()
  const uniqueResourceTypes = Array.from(new Set(logs.map(log => log.resource_type))).sort()

  return (
    <div className="container mx-auto p-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Audit Logs</span>
            <Button onClick={fetchLogs} variant="outline" size="sm">
              ↻ Refresh
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="mb-6 grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Action</label>
              <select
                value={selectedAction}
                onChange={(e) => setSelectedAction(e.target.value)}
                className="w-full p-2 border rounded"
              >
                <option value="all">All Actions</option>
                {uniqueActions.map(action => (
                  <option key={action} value={action}>{action}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Resource Type</label>
              <select
                value={selectedResourceType}
                onChange={(e) => setSelectedResourceType(e.target.value)}
                className="w-full p-2 border rounded"
              >
                <option value="all">All Types</option>
                {uniqueResourceTypes.map(type => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Limit</label>
              <input
                type="number"
                value={filters.limit || 100}
                onChange={(e) => setFilters({ ...filters, limit: parseInt(e.target.value) || 100 })}
                className="w-full p-2 border rounded"
                min="1"
                max="500"
              />
            </div>
            <div className="flex items-end">
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={successOnly}
                  onChange={(e) => setSuccessOnly(e.target.checked)}
                  className="w-4 h-4"
                />
                <span className="text-sm">Success Only</span>
              </label>
            </div>
          </div>

          {/* Logs Table */}
          {loading ? (
            <div className="text-center py-8">Loading audit logs...</div>
          ) : logs.length === 0 ? (
            <div className="text-center py-8 text-gray-500">No audit logs found</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-gray-100">
                    <th className="border p-2 text-left">Timestamp</th>
                    <th className="border p-2 text-left">Action</th>
                    <th className="border p-2 text-left">Resource</th>
                    <th className="border p-2 text-left">IP Address</th>
                    <th className="border p-2 text-left">Endpoint</th>
                    <th className="border p-2 text-left">Status</th>
                    <th className="border p-2 text-left">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => {
                    const details = parseDetails(log.details)
                    return (
                      <tr key={log.id} className="hover:bg-gray-50">
                        <td className="border p-2 text-sm">{formatTimestamp(log.timestamp)}</td>
                        <td className="border p-2">
                          <Badge className={getActionColor(log.action)}>
                            {log.action}
                          </Badge>
                        </td>
                        <td className="border p-2 text-sm">
                          {log.resource_type}
                          {log.resource_id && ` #${log.resource_id}`}
                        </td>
                        <td className="border p-2 text-sm font-mono text-xs">
                          {log.user_ip || 'N/A'}
                        </td>
                        <td className="border p-2 text-sm text-gray-600">
                          {log.endpoint || 'N/A'}
                        </td>
                        <td className="border p-2">
                          {log.success ? (
                            <Badge className="bg-green-500">Success</Badge>
                          ) : (
                            <Badge className="bg-red-500">Failed</Badge>
                          )}
                        </td>
                        <td className="border p-2 text-sm">
                          {details ? (
                            <details className="cursor-pointer">
                              <summary className="text-blue-600 hover:underline">
                                View Details
                              </summary>
                              <pre className="mt-2 p-2 bg-gray-100 rounded text-xs overflow-auto max-w-md">
                                {JSON.stringify(details, null, 2)}
                              </pre>
                            </details>
                          ) : log.error_message ? (
                            <span className="text-red-600 text-xs">{log.error_message}</span>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Summary */}
          <div className="mt-4 text-sm text-gray-600">
            Showing {logs.length} log{logs.length !== 1 ? 's' : ''}
            {selectedAction !== 'all' && ` (filtered by action: ${selectedAction})`}
            {selectedResourceType !== 'all' && ` (filtered by type: ${selectedResourceType})`}
            {successOnly && ' (success only)'}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

