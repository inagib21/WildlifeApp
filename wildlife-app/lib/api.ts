import { Camera, Detection } from '@/types/api'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

export const getCameras = async () => {
  try {
    const response = await axios.get(`${API_URL}/cameras`, {
      timeout: 60000, // 60 second timeout
      headers: {
        'Content-Type': 'application/json'
      }
    })
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

export async function getDetections(filters?: DetectionFilters): Promise<Detection[]> {
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
    return response.data
  } catch (error) {
    console.error('Error fetching detections:', error)
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

export async function getSystemHealth() {
  try {
    const response = await axios.get(`${API_URL}/system`, {
      timeout: 3000 // 3 second timeout (backend optimized to respond quickly)
    })
    const data = response.data
    return {
      ...data, // Return full response including new disk info
      status: data.status || data.motioneye?.status || 'unknown',
      cameras: data.motioneye?.cameras_count || 0,
      detections: 0, // Will be updated when we add detection counting
      motioneye_status: data.motioneye?.status || 'unknown',
      speciesnet_status: data.speciesnet?.status || 'unknown',
      system: data.system
    }
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
      timeout: 30000, // 30 second timeout
      headers: {
        'Content-Type': 'application/json'
      }
    })
    return response.data
  } catch (error: any) {
    console.error('Error syncing cameras from MotionEye:', error)
    // Provide more helpful error messages
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      throw new Error('Request timed out. Please check if the backend server is running.')
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
  } catch (error) {
    console.error('Error fetching species counts:', error)
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
  format?: 'csv' | 'json'
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