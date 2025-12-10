import 'axios'

declare module 'axios' {
  export interface AxiosRequestConfig {
    metadata?: {
      startTime?: number
      duration?: number
    }
  }
  
  export interface InternalAxiosRequestConfig {
    metadata?: {
      startTime?: number
      duration?: number
    }
  }
}

