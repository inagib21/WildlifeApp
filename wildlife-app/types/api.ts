export interface Camera {
  id: number
  name: string
  url: string
  is_active: boolean
  created_at: string
}

export interface Detection {
  id: number
  camera_id: number
  timestamp: string
  species: string
  confidence: number
  image_path: string
  media_url?: string
  file_size?: number
  image_width?: number
  image_height?: number
  image_quality?: number
  camera_name?: string
} 