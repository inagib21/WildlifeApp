import { Camera, Detection } from '@/types/api'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

export const getCameras = async () => {
  try {
    const response = await axios.get(`${API_URL}/cameras`, {
      timeout: 60000 // 60 second timeout
    })
    return response.data
  } catch (error) {
    console.error('Error fetching cameras:', error)
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

export async function getDetections(cameraId?: number, limit?: number): Promise<Detection[]> {
  try {
    const params = new URLSearchParams()
    
    if (cameraId) {
      params.append('camera_id', cameraId.toString())
    }
    
    // Add default limit if not specified
    if (typeof limit === 'number') {
      params.append('limit', limit.toString())
    } else {
      params.append('limit', '50') // Default to 50 detections
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
      status: data.motioneye?.status || 'unknown',
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
    const response = await axios.post(`${API_URL}/cameras/sync`)
    return response.data
  } catch (error) {
    console.error('Error syncing cameras from MotionEye:', error)
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