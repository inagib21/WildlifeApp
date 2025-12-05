import { Camera, Detection } from '@/types/api'
import axios from 'axios'
import { apiCache } from './api-cache'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

export async function getNotificationStatus(): Promise<{ enabled: boolean }> {
  try {
    const response = await axios.get(`${API_URL}/api/notifications/status`, {
      timeout: 5000
    })
    return response.data
  } catch (error: any) {
    console.error('Error fetching notification status:', error)
    return { enabled: false }
  }
}

export async function toggleNotifications(): Promise<{ enabled: boolean; message: string }> {
  try {
    const response = await axios.post(`${API_URL}/api/notifications/toggle`, {}, {
      timeout: 5000
    })
    return response.data
  } catch (error: any) {
    console.error('Error toggling notifications:', error)
    throw error
  }
}

export async function setNotificationEnabled(enabled: boolean): Promise<{ enabled: boolean; message: string }> {
  try {
    const response = await axios.put(`${API_URL}/api/notifications/enabled?enabled=${enabled}`, {}, {
      timeout: 5000
    })
    return response.data
  } catch (error: any) {
    console.error('Error setting notification state:', error)
    throw error
  }
}

export const getCameras = async (useCache: boolean = true) => {
  // Check cache first (5 second TTL for fast page navigation)
  const cacheKey = 'cameras'
  if (useCache) {
    const cached = apiCache.get<Camera[]>(cacheKey)
    if (cached) {
      return cached
    }
  }

  try {
    const response = await axios.get(`${API_URL}/cameras`, {
      timeout: 60000, // 60 second timeout
      headers: {
        'Content-Type': 'application/json'
      }
    })
    // Cache the response for 5 seconds
    if (useCache) {
      apiCache.set(cacheKey, response.data, 5000)
    }
    return response.data
  } catch (error: any) {
    console.error('Error fetching cameras:', error)
    // Provide more helpful error messages
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      console.error('Request timed out. Please check if the backend server is running.')
    } else if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error')) {
      console.error('Cannot connect to backend server. Please ensure the backend is running on port 8001.')
      console.error(`Attempted URL: ${API_URL}/cameras`)
    } else if (error.response) {
      console.error(`Backend returned error: ${error.response.status} - ${error.response.statusText}`)
    }
    return []
  }
}

export const addCamera = async (cameraData: {
  name: string;
  url: string;
  width?: number;
  height?: number;
  framerate?: number;
  stream_quality?: number;
  detection_enabled?: boolean;
}) => {
  const response = await axios.post(`${API_URL}/cameras`, cameraData)
  return response.data
}

export const updateCamera = async (cameraId: number, cameraData: any) => {
  const response = await axios.put(`${API_URL}/cameras/${cameraId}`, cameraData)
  return response.data
}

export const removeCamera = async (cameraId: number) => {
  const response = await axios.delete(`${API_URL}/cameras/${cameraId}`)
  return response.data
}

export interface DetectionFilters {
  cameraId?: number
  limit?: number
  offset?: number
  species?: string
  startDate?: string
  endDate?: string
  search?: string
}

export async function getDetections(filters?: DetectionFilters, useCache: boolean = false): Promise<Detection[]> {
  // Only cache if no filters (or minimal filters) to avoid cache bloat
  const shouldCache = useCache && (!filters || (!filters.search && !filters.startDate && !filters.endDate))
  const cacheKey = `detections:${JSON.stringify(filters || {})}`
  
  if (shouldCache) {
    const cached = apiCache.get<Detection[]>(cacheKey)
    if (cached) {
      return cached
    }
  }

  try {
    const params = new URLSearchParams()
    
    if (filters?.cameraId) {
      params.append('camera_id', filters.cameraId.toString())
    }
    
    if (filters?.species) {
      params.append('species', filters.species)
    }
    
    if (filters?.startDate) {
      params.append('start_date', filters.startDate)
    }
    
    if (filters?.endDate) {
      params.append('end_date', filters.endDate)
    }
    
    if (filters?.search) {
      params.append('search', filters.search)
    }
    
    // Add default limit if not specified
    if (filters?.limit) {
      params.append('limit', filters.limit.toString())
    } else {
      params.append('limit', '50') // Default to 50 detections
    }
    
    if (filters?.offset) {
      params.append('offset', filters.offset.toString())
    }
    
    const url = `${API_URL}/detections?${params.toString()}`
    
    const response = await axios.get(url, {
      timeout: 60000 // 60 second timeout for large responses
    })
    
    // Cache for 3 seconds (detections change frequently)
    if (shouldCache) {
      apiCache.set(cacheKey, response.data, 3000)
    }
    
    return response.data
  } catch (error: any) {
    console.error('Error fetching detections:', error)
    
    // Provide helpful error messages
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      console.error('Request timed out. The backend may be slow or unresponsive.')
    } else if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error') || error.message?.includes('ERR_NETWORK')) {
      console.error('❌ Cannot connect to backend server!')
      console.error(`   Backend URL: ${API_URL}/detections`)
      console.error('   Please ensure the backend is running on port 8001')
      console.error('   Start it with: npm run backend:venv or use scripts\\start-system.bat')
    } else if (error.response) {
      console.error(`Backend returned error: ${error.response.status} - ${error.response.statusText}`)
    } else {
      console.error('Unknown error:', error.message || error)
    }
    
    return []
  }
}

// Legacy function for backward compatibility
export async function getDetectionsLegacy(cameraId?: number, limit?: number): Promise<Detection[]> {
  return getDetections({ cameraId, limit })
}

export async function getDetectionsChunked(cameraId?: number, totalLimit: number = 2000): Promise<Detection[]> {
  try {
    const chunkSize = 500 // Process in chunks of 500
    const allDetections: Detection[] = []
    
    for (let offset = 0; offset < totalLimit; offset += chunkSize) {
      const limit = Math.min(chunkSize, totalLimit - offset)
      const params = new URLSearchParams()
      
      if (cameraId) {
        params.append('camera_id', cameraId.toString())
      }
      params.append('limit', limit.toString())
      params.append('offset', offset.toString())
      
      const url = `${API_URL}/detections?${params.toString()}`
      
      const response = await axios.get(url, {
        timeout: 30000 // 30 second timeout per chunk
      })
      
      const chunkData = response.data
      allDetections.push(...chunkData)
      
      // If we got fewer results than requested, we've reached the end
      if (chunkData.length < limit) {
        break
      }
      
      // Small delay between chunks to prevent overwhelming the server
      if (offset + chunkSize < totalLimit) {
        await new Promise(resolve => setTimeout(resolve, 100))
      }
    }
    
    return allDetections
  } catch (error) {
    console.error('Error fetching detections chunked:', error)
    return []
  }
}

export async function createDetection(detection: Omit<Detection, 'id'>): Promise<Detection> {
  const response = await axios.post(`${API_URL}/detections`, detection)
  return response.data
}

export async function getSystemHealth(useCache: boolean = true) {
  // Check cache first (3 second TTL for fast page navigation)
  const cacheKey = 'system_health'
  if (useCache) {
    const cached = apiCache.get<any>(cacheKey)
    if (cached) {
      return cached
    }
  }

  try {
    const response = await axios.get(`${API_URL}/system`, {
      timeout: 3000 // 3 second timeout (backend optimized to respond quickly)
    })
    const data = response.data
    const result = {
      ...data, // Return full response including new disk info
      status: data.status || data.motioneye?.status || 'unknown',
      cameras: data.motioneye?.cameras_count || 0,
      detections: 0, // Will be updated when we add detection counting
      motioneye_status: data.motioneye?.status || 'unknown',
      speciesnet_status: data.speciesnet?.status || 'unknown',
      system: data.system
    }
    // Cache for 3 seconds
    if (useCache) {
      apiCache.set(cacheKey, result, 3000)
    }
    return result
  } catch (error: any) {
    // Handle timeout gracefully - don't retry, just return default values
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      console.warn('System health check timeout - returning default values')
      return {
        status: 'timeout',
        cameras: 0,
        detections: 0,
        motioneye_status: 'timeout',
        speciesnet_status: 'timeout',
        system: {
          cpu_percent: 0,
          memory_percent: 0,
          disk_percent: 0,
          timestamp: new Date().toISOString()
        }
      }
    }
    
    console.error('Error fetching system health:', error)
    // Return default values instead of throwing - don't break the UI
    return {
      status: 'error',
      cameras: 0,
      detections: 0,
      motioneye_status: 'error',
      speciesnet_status: 'error',
      system: {
        cpu_percent: 0,
        memory_percent: 0,
        disk_percent: 0,
        timestamp: new Date().toISOString()
      }
    }
  }
}

export async function getCameraStream(cameraId: number) {
  try {
    const response = await axios.get(`${API_URL}/stream/${cameraId}`)
    return response.data
  } catch (error) {
    console.error('Error fetching camera stream:', error)
    return null
  }
}

export async function syncCamerasFromMotionEye() {
  try {
    const response = await axios.post(`${API_URL}/cameras/sync`, {}, {
      timeout: 60000, // 60 second timeout (increased for MotionEye sync)
      headers: {
        'Content-Type': 'application/json'
      }
    })
    return response.data
  } catch (error: any) {
    console.error('Error syncing cameras from MotionEye:', error)
    // Provide more helpful error messages
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      throw new Error('Request timed out. The sync operation may be taking longer than expected, or MotionEye may not be responding. Please check if MotionEye is running at http://localhost:8765')
    } else if (error.response?.status === 503) {
      // Service unavailable - MotionEye not accessible
      throw new Error(error.response.data?.detail || 'MotionEye is not accessible. Please ensure MotionEye is running.')
    } else if (error.response?.status === 500) {
      // Server error
      throw new Error(error.response.data?.detail || 'Error syncing cameras from MotionEye')
    } else if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error')) {
      throw new Error('Cannot connect to backend server. Please ensure the backend is running on port 8001.')
    }
    if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error') || error.message?.includes('ERR_CONNECTION_REFUSED')) {
      throw new Error('Cannot connect to backend server. Please ensure the backend is running on port 8001.')
    }
    // Check if it's an axios error with no response (backend not running)
    if (error.response === undefined && error.request !== undefined) {
      throw new Error('Cannot connect to backend server. Please ensure the backend is running on port 8001.')
    }
    // If backend returned an error, pass it through
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail)
    }
    throw error
  }
}

export interface AuditLog {
  id: number
  timestamp: string
  action: string
  resource_type: string
  resource_id?: number
  user_ip?: string
  user_agent?: string
  endpoint?: string
  details?: string
  success: boolean
  error_message?: string
}

export interface AuditLogFilters {
  limit?: number
  offset?: number
  action?: string
  resource_type?: string
  resource_id?: number
  success_only?: boolean
}

export async function getAuditLogs(filters?: AuditLogFilters): Promise<AuditLog[]> {
  try {
    const params = new URLSearchParams()
    
    if (filters?.limit) {
      params.append('limit', filters.limit.toString())
    }
    if (filters?.offset) {
      params.append('offset', filters.offset.toString())
    }
    if (filters?.action) {
      params.append('action', filters.action)
    }
    if (filters?.resource_type) {
      params.append('resource_type', filters.resource_type)
    }
    if (filters?.resource_id) {
      params.append('resource_id', filters.resource_id.toString())
    }
    if (filters?.success_only) {
      params.append('success_only', 'true')
    }
    
    const url = `${API_URL}/api/audit-logs${params.toString() ? `?${params.toString()}` : ''}`
    
    const response = await axios.get(url, {
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    })
    return response.data
  } catch (error: any) {
    console.error('Error fetching audit logs:', error)
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      throw new Error('Request timed out. Please check if the backend server is running.')
    }
    if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error') || error.message?.includes('ERR_CONNECTION_REFUSED')) {
      throw new Error('Cannot connect to backend server. Please ensure the backend is running on port 8001.')
    }
    if (error.response === undefined && error.request !== undefined) {
      throw new Error('Cannot connect to backend server. Please ensure the backend is running on port 8001.')
    }
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail)
    }
    throw error
  }
}

export async function processImageWithSpeciesNet(file: File, cameraId?: number) {
  try {
    const formData = new FormData()
    formData.append('file', file)
    if (cameraId) {
      formData.append('camera_id', cameraId.toString())
    }
    
    const response = await axios.post(`${API_URL}/process-image`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  } catch (error) {
    console.error('Error processing image with SpeciesNet:', error)
    throw error
  }
}

export async function getDetectionsCount(cameraId?: number): Promise<number> {
  try {
    const params = new URLSearchParams()
    if (cameraId) {
      params.append('camera_id', cameraId.toString())
    }
    
    const url = `${API_URL}/detections/count?${params.toString()}`
    
    const response = await axios.get(url, {
      timeout: 60000 // 60 second timeout
    })
    return response.data.count
  } catch (error) {
    console.error('Error fetching detections count:', error)
    return 0
  }
}

export async function getSpeciesCounts(range: 'week' | 'month' | 'all' = 'all'): Promise<Array<{species: string, count: number}>> {
  try {
    const url = `${API_URL}/detections/species-counts?range=${range}`
    
    const response = await axios.get(url, {
      timeout: 60000 // 60 second timeout
    })
    return response.data
  } catch (error: any) {
    console.error('Error fetching species counts:', error)
    
    // Provide helpful error messages
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      console.error('Request timed out. The backend may be slow or unresponsive.')
    } else if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error') || error.message?.includes('ERR_NETWORK')) {
      console.error('❌ Cannot connect to backend server!')
      console.error(`   Backend URL: ${API_URL}/detections/species-counts`)
      console.error('   Please ensure the backend is running on port 8001')
    } else if (error.response) {
      console.error(`Backend returned error: ${error.response.status} - ${error.response.statusText}`)
    }
    
    return []
  }
}

export async function getUniqueSpeciesCount(): Promise<number> {
  try {
    const response = await axios.get(`${API_URL}/detections/unique-species-count`, {
      timeout: 60000 // 60 second timeout
    })
    return response.data.count
  } catch (error) {
    console.error('Error fetching unique species count:', error)
    return 0
  }
}

export async function getDetectionsTimeseries(interval: 'hour' | 'day' = 'hour', days: number = 7): Promise<Array<{bucket: string, count: number}>> {
  try {
    const url = `${API_URL}/analytics/detections/timeseries?interval=${interval}&days=${days}`
    const response = await axios.get(url, { timeout: 30000 })
    return response.data
  } catch (error) {
    console.error('Error fetching detections timeseries:', error)
    return []
  }
}

export async function getTopSpecies(limit: number = 5, days: number = 30): Promise<Array<{species: string, count: number}>> {
  try {
    const url = `${API_URL}/analytics/detections/top_species?limit=${limit}&days=${days}`
    const response = await axios.get(url, { timeout: 30000 })
    return response.data
  } catch (error) {
    console.error('Error fetching top species:', error)
    return []
  }
}

export async function getUniqueSpeciesCountFast(days: number = 30): Promise<number> {
  try {
    const url = `${API_URL}/analytics/detections/unique_species_count?days=${days}`
    const response = await axios.get(url, { timeout: 30000 })
    return response.data.unique_species
  } catch (error) {
    console.error('Error fetching unique species count (fast):', error)
    return 0
  }
}

export interface ExportOptions {
  format?: 'csv' | 'json' | 'pdf'
  cameraId?: number
  species?: string
  startDate?: string
  endDate?: string
  limit?: number
}

export async function exportDetections(options: ExportOptions = {}): Promise<Blob> {
  try {
    const params = new URLSearchParams()
    
    params.append('format', options.format || 'csv')
    
    if (options.cameraId) {
      params.append('camera_id', options.cameraId.toString())
    }
    if (options.species) {
      params.append('species', options.species)
    }
    if (options.startDate) {
      params.append('start_date', options.startDate)
    }
    if (options.endDate) {
      params.append('end_date', options.endDate)
    }
    if (options.limit) {
      params.append('limit', options.limit.toString())
    }
    
    const url = `${API_URL}/api/detections/export?${params.toString()}`
    
    const response = await axios.get(url, {
      responseType: 'blob',
      timeout: 120000 // 2 minute timeout for large exports
    })
    
    return response.data
  } catch (error: any) {
    console.error('Error exporting detections:', error)
    throw new Error(error.response?.data?.detail || 'Failed to export detections')
  }
}

export async function deleteDetection(detectionId: number): Promise<void> {
  try {
    await axios.delete(`${API_URL}/detections/${detectionId}`, {
      timeout: 10000
    })
  } catch (error: any) {
    console.error('Error deleting detection:', error)
    throw new Error(error.response?.data?.detail || 'Failed to delete detection')
  }
}

export async function bulkDeleteDetections(detectionIds: number[]): Promise<{ deleted_count: number }> {
  try {
    const response = await axios.post(
      `${API_URL}/detections/bulk-delete`,
      detectionIds,
      {
        headers: { 'Content-Type': 'application/json' },
        timeout: 30000
      }
    )
    return response.data
  } catch (error: any) {
    console.error('Error bulk deleting detections:', error)
    throw new Error(error.response?.data?.detail || 'Failed to delete detections')
  }
}

export async function getScheduledJobs(): Promise<Array<{ id: string; name: string; next_run: string | null; trigger: string }>> {
  try {
    const response = await axios.get(`${API_URL}/api/scheduler/jobs`, {
      timeout: 5000
    })
    return response.data.jobs || []
  } catch (error: any) {
    console.error('Error fetching scheduled jobs:', error)
    return []
  }
}

export interface SpeciesAnalytics {
  species: Array<{
    species: string
    count: number
    average_confidence: number
    detections: Array<{
      id: number
      timestamp: string
      confidence: number
      camera_id: number
    }>
  }>
  total_detections: number
  unique_species: number
}

export interface TimelineAnalytics {
  timeline: Array<{
    date: string
    count: number
    species: Record<string, number>
  }>
  interval: string
  total_points: number
}

export interface CameraAnalytics {
  cameras: Array<{
    camera_id: number
    camera_name: string
    count: number
    average_confidence: number
    top_species: Array<{
      species: string
      count: number
    }>
  }>
  total_detections: number
  total_cameras: number
}

export async function getSpeciesAnalytics(
  startDate?: string,
  endDate?: string,
  cameraId?: number
): Promise<SpeciesAnalytics> {
  try {
    const params = new URLSearchParams()
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    if (cameraId) params.append('camera_id', cameraId.toString())
    
    const response = await axios.get(`${API_URL}/api/analytics/species?${params.toString()}`, {
      timeout: 60000 // Increased timeout to 60s for large datasets
    })
    return response.data
  } catch (error: any) {
    console.error('Error fetching species analytics:', error)
    
    // Provide more helpful error messages
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      console.error('Request timed out. The backend may be slow processing large datasets.')
    } else if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error')) {
      console.error('Cannot connect to backend server. Please ensure the backend is running on port 8001.')
    } else if (error.response) {
      console.error(`Backend returned error: ${error.response.status} - ${error.response.statusText}`)
      console.error(`Error details: ${error.response.data?.detail || 'Unknown error'}`)
    }
    
    throw new Error(error.response?.data?.detail || error.message || 'Failed to fetch species analytics')
  }
}

export async function getTimelineAnalytics(
  startDate?: string,
  endDate?: string,
  cameraId?: number,
  interval: 'day' | 'week' | 'month' = 'day'
): Promise<TimelineAnalytics> {
  try {
    const params = new URLSearchParams()
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    if (cameraId) params.append('camera_id', cameraId.toString())
    params.append('interval', interval)
    
    const response = await axios.get(`${API_URL}/api/analytics/timeline?${params.toString()}`, {
      timeout: 60000 // Increased timeout to 60s for large datasets
    })
    return response.data
  } catch (error: any) {
    console.error('Error fetching timeline analytics:', error)
    
    // Provide more helpful error messages
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      console.error('Request timed out. The backend may be slow processing large datasets.')
    } else if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error')) {
      console.error('Cannot connect to backend server. Please ensure the backend is running on port 8001.')
    } else if (error.response) {
      console.error(`Backend returned error: ${error.response.status} - ${error.response.statusText}`)
      console.error(`Error details: ${error.response.data?.detail || 'Unknown error'}`)
    }
    
    throw new Error(error.response?.data?.detail || error.message || 'Failed to fetch timeline analytics')
  }
}

export async function getCameraAnalytics(
  startDate?: string,
  endDate?: string
): Promise<CameraAnalytics> {
  try {
    const params = new URLSearchParams()
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    
    const response = await axios.get(`${API_URL}/api/analytics/cameras?${params.toString()}`, {
      timeout: 60000 // Increased timeout to 60s for large datasets
    })
    return response.data
  } catch (error: any) {
    console.error('Error fetching camera analytics:', error)
    
    // Provide more helpful error messages
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      console.error('Request timed out. The backend may be slow processing large datasets.')
    } else if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error')) {
      console.error('Cannot connect to backend server. Please ensure the backend is running on port 8001.')
    } else if (error.response) {
      console.error(`Backend returned error: ${error.response.status} - ${error.response.statusText}`)
      console.error(`Error details: ${error.response.data?.detail || 'Unknown error'}`)
    }
    
    throw new Error(error.response?.data?.detail || error.message || 'Failed to fetch camera analytics')
  }
}

export interface HealthCheck {
  status: 'healthy' | 'degraded' | 'error'
  timestamp: string
  dependencies: {
    database: {
      status: string
      required: boolean
      query_time_ms?: number
      error?: string
      stats?: {
        detections: number | null
        cameras: number | null
      }
    }
    motioneye: {
      status: string
      required: boolean
      response_time_ms?: number
      error?: string
    }
    speciesnet: {
      status: string
      required: boolean
      response_time_ms?: number
      error?: string
    }
  }
  system?: {
    cpu_percent: number | null
    memory: {
      total_gb: number | null
      used_gb: number | null
      available_gb: number | null
      percent: number | null
    } | null
    disk: {
      total_gb: number | null
      used_gb: number | null
      free_gb: number | null
      percent: number | null
    } | null
  }
  uptime_seconds: number | null
}

export async function getHealthCheck(detailed: boolean = false): Promise<HealthCheck> {
  try {
    const endpoint = detailed ? '/health/detailed' : '/health'
    const response = await axios.get(`${API_URL}${endpoint}`, {
      timeout: 5000
    })
    return response.data
  } catch (error: any) {
    console.error('Error fetching health check:', error)
    throw new Error(error.response?.data?.detail || 'Failed to fetch health check')
  }
}

export async function cleanupAuditLogs(retentionDays: number = 90): Promise<{ deleted_count: number }> {
  try {
    const response = await axios.post(
      `${API_URL}/api/audit-logs/cleanup`,
      null,
      {
        params: { retention_days: retentionDays },
        timeout: 30000
      }
    )
    return response.data
  } catch (error: any) {
    console.error('Error cleaning up audit logs:', error)
    throw new Error(error.response?.data?.detail || 'Failed to cleanup audit logs')
  }
}

export async function getAuditLogStats(): Promise<{
  total_count: number
  by_action: Record<string, number>
  by_resource_type: Record<string, number>
  success_rate: {
    success: number
    failure: number
    success_percentage: number
  }
  date_range: {
    oldest: string | null
    newest: string | null
  }
}> {
  try {
    const response = await axios.get(`${API_URL}/api/audit-logs/stats`, {
      timeout: 5000
    })
    return response.data
  } catch (error: any) {
    console.error('Error fetching audit log stats:', error)
    throw new Error(error.response?.data?.detail || 'Failed to fetch audit log stats')
  }
}

export interface ArchivalStats {
  total_archived: number
  by_species: Record<string, number>
  by_camera: Record<string, number>
  by_date: Record<string, number>
  high_confidence_count: number
  total_size_gb: number
}

export async function archiveImages(limit: number = 100): Promise<{
  success: boolean
  stats: {
    processed: number
    archived: number
    skipped: number
    errors: number
  }
  message: string
}> {
  try {
    const response = await axios.post(
      `${API_URL}/api/archival/archive`,
      null,
      {
        params: { limit },
        timeout: 300000  // 5 minutes for large batches
      }
    )
    return response.data
  } catch (error: any) {
    console.error('Error archiving images:', error)
    throw new Error(error.response?.data?.detail || 'Failed to archive images')
  }
}

export async function getArchivalStats(): Promise<ArchivalStats> {
  try {
    const response = await axios.get(`${API_URL}/api/archival/stats`, {
      timeout: 10000
    })
    return response.data
  } catch (error: any) {
    console.error('Error fetching archival stats:', error)
    throw new Error(error.response?.data?.detail || 'Failed to fetch archival stats')
  }
}

export async function cleanupOldArchives(
  maxAgeDays: number = 365,
  dryRun: boolean = false
): Promise<{
  success: boolean
  stats: {
    checked: number
    deleted: number
    errors: number
    freed_gb: number
  }
  dry_run: boolean
  message: string
}> {
  try {
    const response = await axios.post(
      `${API_URL}/api/archival/cleanup`,
      null,
      {
        params: {
          max_age_days: maxAgeDays,
          dry_run: dryRun
        },
        timeout: 300000  // 5 minutes for large cleanup operations
      }
    )
    return response.data
  } catch (error: any) {
    console.error('Error cleaning up archives:', error)
    throw new Error(error.response?.data?.detail || 'Failed to cleanup archives')
  }
}

export interface AdvancedMonitoring {
  timestamp: string
  disk_io: {
    current: {
      read_bytes: number
      write_bytes: number
      read_rate_bps: number
      write_rate_bps: number
    }
    average: {
      read_rate_bps: number
      write_rate_bps: number
    }
    history_count: number
  }
  network_io: {
    current: {
      bytes_sent: number
      bytes_recv: number
      sent_rate_bps: number
      recv_rate_bps: number
    }
    average: {
      sent_rate_bps: number
      recv_rate_bps: number
    }
    history_count: number
  }
  camera_health: Array<{
    service: string
    status: string
    response_time_ms: number | null
    cameras_count?: number
    error?: string
    timestamp: string
  }>
  speciesnet_health: {
    service: string
    status: string
    response_time_ms: number | null
    error?: string
    timestamp: string
  } | null
  system_uptime: {
    boot_time: string
    uptime_seconds: number
    uptime_days: number
    uptime_hours: number
    uptime_minutes: number
  }
  process_info?: {
    cpu_percent: number
    memory_mb: number
    num_threads: number
    create_time: string
  }
  error?: string
  status?: string
}

export async function getAdvancedMonitoring(): Promise<AdvancedMonitoring> {
  try {
    const response = await axios.get(`${API_URL}/api/system/advanced`, {
      timeout: 10000
    })
    return response.data
  } catch (error: any) {
    console.error('Error fetching advanced monitoring:', error)
    throw new Error(error.response?.data?.detail || 'Failed to fetch advanced monitoring')
  }
}

export interface TaskInfo {
  task_id: string
  task_type: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  created_at: string
  started_at?: string | null
  completed_at?: string | null
  progress: number
  message?: string | null
  result?: Record<string, any> | null
  error?: string | null
  metadata?: Record<string, any> | null
}

export async function processImageAsync(
  file: File,
  cameraId?: number,
  compress: boolean = true
): Promise<{ task_id: string; status: string; message: string }> {
  try {
    const formData = new FormData()
    formData.append('file', file)
    if (cameraId) formData.append('camera_id', cameraId.toString())
    formData.append('compress', compress.toString())
    formData.append('async_mode', 'true')

    const response = await axios.post(`${API_URL}/process-image`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 5000
    })
    return response.data
  } catch (error: any) {
    console.error('Error starting async image processing:', error)
    throw new Error(error.response?.data?.detail || 'Failed to start image processing')
  }
}

export async function getTaskStatus(taskId: string): Promise<TaskInfo> {
  try {
    const response = await axios.get(`${API_URL}/api/tasks/${taskId}`, {
      timeout: 5000
    })
    return response.data
  } catch (error: any) {
    console.error('Error fetching task status:', error)
    throw new Error(error.response?.data?.detail || 'Failed to fetch task status')
  }
}

export async function listTasks(
  taskType?: string,
  status?: string,
  limit: number = 100,
  offset: number = 0
): Promise<{ tasks: TaskInfo[]; total: number; limit: number; offset: number }> {
  try {
    const params = new URLSearchParams()
    if (taskType) params.append('task_type', taskType)
    if (status) params.append('status', status)
    params.append('limit', limit.toString())
    params.append('offset', offset.toString())

    const response = await axios.get(`${API_URL}/api/tasks?${params.toString()}`, {
      timeout: 5000
    })
    return response.data
  } catch (error: any) {
    console.error('Error listing tasks:', error)
    throw new Error(error.response?.data?.detail || 'Failed to list tasks')
  }
}

export async function cancelTask(taskId: string): Promise<{ success: boolean; message: string }> {
  try {
    const response = await axios.post(`${API_URL}/api/tasks/${taskId}/cancel`, null, {
      timeout: 5000
    })
    return response.data
  } catch (error: any) {
    console.error('Error cancelling task:', error)
    throw new Error(error.response?.data?.detail || 'Failed to cancel task')
  }
}

export async function getTaskStats(): Promise<{
  total: number
  by_status: Record<string, number>
  by_type: Record<string, number>
  running: number
  completed: number
  failed: number
}> {
  try {
    const response = await axios.get(`${API_URL}/api/tasks/stats`, {
      timeout: 5000
    })
    return response.data
  } catch (error: any) {
    console.error('Error fetching task stats:', error)
    throw new Error(error.response?.data?.detail || 'Failed to fetch task stats')
  }
}

export interface ApiKeyInfo {
  id: number
  user_name: string
  description?: string | null
  is_active: boolean
  created_at: string | null
  last_used_at: string | null
  expires_at: string | null
  usage_count: number
  rate_limit_per_minute: number
  allowed_ips?: string[] | null
  is_expired: boolean
}

export async function createApiKey(
  userName: string,
  description?: string,
  expiresInDays?: number,
  rateLimitPerMinute: number = 60,
  allowedIps?: string
): Promise<{
  api_key: string
  key_hash: string
  user_name: string
  message: string
}> {
  try {
    const params: any = {
      user_name: userName,
      rate_limit_per_minute: rateLimitPerMinute
    }
    if (description) params.description = description
    if (expiresInDays) params.expires_in_days = expiresInDays
    if (allowedIps) params.allowed_ips = allowedIps

    const response = await axios.post(`${API_URL}/api/keys`, null, {
      params,
      timeout: 10000
    })
    return response.data
  } catch (error: any) {
    console.error('Error creating API key:', error)
    throw new Error(error.response?.data?.detail || 'Failed to create API key')
  }
}

export async function listApiKeys(
  userName?: string,
  activeOnly: boolean = true,
  limit: number = 100,
  offset: number = 0
): Promise<{
  keys: ApiKeyInfo[]
  total: number
  limit: number
  offset: number
}> {
  try {
    const params = new URLSearchParams()
    if (userName) params.append('user_name', userName)
    params.append('active_only', activeOnly.toString())
    params.append('limit', limit.toString())
    params.append('offset', offset.toString())

    const response = await axios.get(`${API_URL}/api/keys?${params.toString()}`, {
      timeout: 5000
    })
    return response.data
  } catch (error: any) {
    console.error('Error listing API keys:', error)
    throw new Error(error.response?.data?.detail || 'Failed to list API keys')
  }
}

export async function getApiKeyStats(keyId: number): Promise<ApiKeyInfo> {
  try {
    const response = await axios.get(`${API_URL}/api/keys/${keyId}`, {
      timeout: 5000
    })
    return response.data
  } catch (error: any) {
    console.error('Error fetching API key stats:', error)
    throw new Error(error.response?.data?.detail || 'Failed to fetch API key stats')
  }
}

export async function revokeApiKey(keyId: number): Promise<{ success: boolean; message: string }> {
  try {
    const response = await axios.post(`${API_URL}/api/keys/${keyId}/revoke`, null, {
      timeout: 5000
    })
    return response.data
  } catch (error: any) {
    console.error('Error revoking API key:', error)
    throw new Error(error.response?.data?.detail || 'Failed to revoke API key')
  }
}

export async function rotateApiKey(
  keyId: number,
  userName: string,
  description?: string
): Promise<{
  api_key: string
  key_hash: string
  user_name: string
  message: string
}> {
  try {
    const params: any = { user_name: userName }
    if (description) params.description = description

    const response = await axios.post(`${API_URL}/api/keys/${keyId}/rotate`, null, {
      params,
      timeout: 10000
    })
    return response.data
  } catch (error: any) {
    console.error('Error rotating API key:', error)
    throw new Error(error.response?.data?.detail || 'Failed to rotate API key')
  }
} 