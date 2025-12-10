/**
 * API Debugging Utilities
 * Provides enhanced error handling and debugging for API calls
 */

import axios, { AxiosError, AxiosRequestConfig, AxiosResponse } from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

export interface ApiError {
  message: string
  status?: number
  statusText?: string
  endpoint?: string
  errorType?: string
  details?: any
  timestamp: string
}

export class ApiDebugger {
  private static enabled = process.env.NODE_ENV === 'development' || 
                          (typeof window !== 'undefined' && localStorage.getItem('api_debug') === 'true')

  static enable() {
    this.enabled = true
    if (typeof window !== 'undefined') {
      localStorage.setItem('api_debug', 'true')
    }
  }

  static disable() {
    this.enabled = false
    if (typeof window !== 'undefined') {
      localStorage.removeItem('api_debug')
    }
  }

  static logRequest(config: AxiosRequestConfig) {
    if (!this.enabled) return
    
    console.group(`🔵 [API Request] ${config.method?.toUpperCase()} ${config.url}`)
    console.debug('Config:', {
      method: config.method,
      url: config.url,
      baseURL: config.baseURL,
      params: config.params,
      headers: config.headers,
      timeout: config.timeout
    })
    console.groupEnd()
  }

  static logResponse(response: AxiosResponse) {
    if (!this.enabled) return
    
    const duration = response.config.metadata?.duration || 0
    console.group(`🟢 [API Response] ${response.config.method?.toUpperCase()} ${response.config.url} (${duration.toFixed(2)}ms)`)
    console.debug('Response:', {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
      data: response.data
    })
    console.groupEnd()
  }

  static logError(error: AxiosError | Error | unknown, context?: string) {
    try {
      // Handle null, undefined, or empty error objects
      if (!error) {
        const fallbackError: ApiError = {
          message: 'Unknown error: error object is null or undefined',
          timestamp: new Date().toISOString(),
          endpoint: context || 'Unknown',
          errorType: 'UnknownError'
        }
        console.group(`🔴 [API Error] ${fallbackError.endpoint}`)
        console.error('Error Details:', fallbackError)
        console.error('Raw Error:', error)
        console.groupEnd()
        return fallbackError
      }

      // Safely extract error message with multiple fallbacks
      let errorMessage = 'Unknown error'
      try {
        if (error instanceof Error) {
          errorMessage = error.message || error.name || String(error) || 'Unknown error'
        } else if (typeof error === 'string') {
          errorMessage = error
        } else if (typeof error === 'object' && error !== null) {
          // Try to extract message from object - check multiple common properties
          const errorObj = error as any
          errorMessage = errorObj.message || 
                        errorObj.error || 
                        errorObj.detail || 
                        errorObj.msg ||
                        errorObj.errorMessage ||
                        errorObj.Error ||
                        (typeof errorObj.toString === 'function' ? errorObj.toString() : String(error)) || 
                        'Unknown error'
        } else if (error !== null && error !== undefined) {
          errorMessage = String(error) || 'Unknown error'
        }
      } catch (extractError) {
        // If we can't extract the message, use a fallback
        errorMessage = 'Error occurred but message could not be extracted'
        console.warn('Failed to extract error message:', extractError)
      }
      
      const errorInfo: ApiError = {
        message: errorMessage || 'Unknown error occurred',
        timestamp: new Date().toISOString(),
        endpoint: context || 'Unknown'
      }

      if (axios.isAxiosError(error)) {
        errorInfo.status = error.response?.status
        errorInfo.statusText = error.response?.statusText
        errorInfo.endpoint = error.config?.url || context
        errorInfo.errorType = 'AxiosError'
        
        // Update error message with more specific Axios error info
        if (!errorInfo.message || errorInfo.message === 'Unknown error') {
          if (error.message) {
            errorInfo.message = error.message
          } else if (error.code) {
            errorInfo.message = `Network error: ${error.code}`
          } else if (error.response?.statusText) {
            errorInfo.message = `HTTP ${error.response.status}: ${error.response.statusText}`
          }
        }
        
        // Safely extract request details - only include defined, meaningful values
        const requestDetails: any = {}
        if (error.config) {
          if (error.config.method) requestDetails.method = error.config.method
          if (error.config.url) requestDetails.url = error.config.url
          if (error.config.baseURL) requestDetails.baseURL = error.config.baseURL
          if (error.config.timeout) requestDetails.timeout = error.config.timeout
          // Only include safe, serializable data
          if (error.config.params !== undefined && error.config.params !== null) {
            try {
              requestDetails.params = JSON.parse(JSON.stringify(error.config.params))
            } catch (e) {
              requestDetails.params = String(error.config.params)
            }
          }
        }
        
        // Safely extract response details - only include defined values
        const responseDetails: any = {}
        if (error.response) {
          if (error.response.status !== undefined) responseDetails.status = error.response.status
          if (error.response.statusText) responseDetails.statusText = error.response.statusText
          if (error.response.data !== undefined && error.response.data !== null) {
            try {
              // Try to serialize response data
              if (typeof error.response.data === 'string') {
                responseDetails.data = error.response.data
              } else {
                responseDetails.data = JSON.parse(JSON.stringify(error.response.data))
              }
            } catch (e) {
              // If serialization fails, convert to string
              try {
                responseDetails.data = String(error.response.data)
              } catch (e2) {
                responseDetails.data = 'Unable to serialize response data'
              }
            }
          }
        } else if (error.request) {
          // No response received - network error
          responseDetails.note = 'No response received from server'
          if (error.code) {
            responseDetails.code = error.code
          }
        }
        
        // Build details object with only non-empty, meaningful values
        const details: any = {}
        const requestKeys = Object.keys(requestDetails).filter(key => {
          const val = requestDetails[key]
          return val !== undefined && val !== null && val !== 'unknown'
        })
        if (requestKeys.length > 0) {
          // Only include keys that have meaningful values
          const meaningfulRequest: any = {}
          requestKeys.forEach(key => {
            meaningfulRequest[key] = requestDetails[key]
          })
          details.request = meaningfulRequest
        }
        
        const responseKeys = Object.keys(responseDetails).filter(key => {
          const val = responseDetails[key]
          return val !== undefined && val !== null
        })
        // Include response details if available, even for network errors (no response but has request)
        if (responseKeys.length > 0) {
          // Only include keys that have meaningful values
          const meaningfulResponse: any = {}
          responseKeys.forEach(key => {
            meaningfulResponse[key] = responseDetails[key]
          })
          details.response = meaningfulResponse
        }
        
        if (error.code) {
          details.code = error.code
        }
        if (error.message) {
          details.message = error.message
        }
        
        // Only set details if it has actual meaningful content
        // Recursively check that nested objects aren't empty
        const detailKeys = Object.keys(details).filter(key => {
          const value = details[key]
          if (value === undefined || value === null) return false
          if (typeof value === 'object' && !Array.isArray(value)) {
            // For nested objects, check if they have any non-empty properties
            const nestedKeys = Object.keys(value).filter(nestedKey => {
              const nestedValue = value[nestedKey]
              if (nestedValue === undefined || nestedValue === null) return false
              if (typeof nestedValue === 'object' && !Array.isArray(nestedValue) && Object.keys(nestedValue).length === 0) return false
              return true
            })
            return nestedKeys.length > 0
          }
          return true
        })
        if (detailKeys.length > 0) {
          errorInfo.details = details
        }
      } else {
        errorInfo.errorType = (error && typeof error === 'object' && 'constructor' in error && error.constructor?.name) 
          ? String(error.constructor.name) 
          : 'Error'
        
        // Build details object with only non-empty values
        const details: any = {}
        if (error && typeof error === 'object' && 'message' in error) {
          const errorObj = error as { message?: any }
          if (errorObj.message) {
            details.message = errorObj.message
          }
        }
        if (error && typeof error === 'object' && 'stack' in error) {
          const errorObj = error as { stack?: any }
          if (errorObj.stack) {
            details.stack = errorObj.stack
          }
        }
        if (error && typeof error === 'object' && 'name' in error) {
          const errorObj = error as { name?: any }
          if (errorObj.name) {
            details.name = errorObj.name
          }
        }
        
        // Only set details if it has content
        if (Object.keys(details).length > 0) {
          errorInfo.details = details
        }
      }

    // Build error info for logging - ensure we always have content
    const endpointName = errorInfo.endpoint || context || 'Unknown'
    
    console.group(`🔴 [API Error] ${endpointName}`)
    
    // Always log basic error info - ensure message is never empty
    // Use errorInfo.message which was already extracted earlier
    const basicInfo: any = {
      message: errorInfo.message || 'Unknown error occurred',
      timestamp: errorInfo.timestamp || new Date().toISOString(),
      endpoint: endpointName || 'Unknown'
    }
    
    // Add status info if available
    if (errorInfo.status !== undefined && errorInfo.status !== null) {
      basicInfo.status = errorInfo.status
    }
    if (errorInfo.statusText) {
      basicInfo.statusText = errorInfo.statusText
    }
    if (errorInfo.errorType) {
      basicInfo.errorType = errorInfo.errorType
    }
    
    // Log basic info first - ensure it always has content
    if (!basicInfo.message || basicInfo.message.trim() === '') {
      basicInfo.message = 'Unknown error occurred'
    }
    console.error('Error Details:', basicInfo)
    
    // Add details if available - only log meaningful, non-empty details
    if (errorInfo.details && Object.keys(errorInfo.details).length > 0) {
      const filteredDetails: any = {}
      
      // Build a filtered details object with only meaningful values
      for (const key of Object.keys(errorInfo.details)) {
        const val = errorInfo.details[key]
        if (val === undefined || val === null) continue
        
        // Skip empty objects and arrays
        if (typeof val === 'object' && !Array.isArray(val)) {
          if (Object.keys(val).length === 0) continue
          // Recursively filter nested objects
          const nestedKeys = Object.keys(val).filter(k => {
            const nestedVal = val[k]
            return nestedVal !== undefined && nestedVal !== null && 
                   (typeof nestedVal !== 'object' || Array.isArray(nestedVal) || Object.keys(nestedVal).length > 0)
          })
          if (nestedKeys.length > 0) {
            const filteredNested: any = {}
            nestedKeys.forEach(k => {
              filteredNested[k] = val[k]
            })
            filteredDetails[key] = filteredNested
          }
        } else if (Array.isArray(val)) {
          // Include arrays even if empty (might be meaningful)
          filteredDetails[key] = val
        } else {
          // Include primitive values
          filteredDetails[key] = val
        }
      }
      
      // Only log if we have meaningful details after filtering
      if (Object.keys(filteredDetails).length > 0) {
        console.error('Error Details (extended):', filteredDetails)
      }
    }
    
    // Always log raw error for full context
    if (error && axios.isAxiosError(error)) {
      const axiosDetails: any = {}
      if (error.code) axiosDetails.code = error.code
      if (error.message) axiosDetails.message = error.message
      if (error.config?.url) axiosDetails.url = error.config.url
      if (error.config?.method) axiosDetails.method = error.config.method
      if (error.config?.baseURL) axiosDetails.baseURL = error.config.baseURL
      if (error.response) {
        axiosDetails.response = {
          status: error.response.status,
          statusText: error.response.statusText,
          data: error.response.data
        }
      }
      if (Object.keys(axiosDetails).length > 0) {
        console.error('Axios Error Details:', axiosDetails)
      }
    } else if (error && error instanceof Error) {
      const errorObj: any = {}
      if (error.name) errorObj.name = error.name
      if (error.message) errorObj.message = error.message
      if (error.stack) errorObj.stack = error.stack
      if (Object.keys(errorObj).length > 0) {
        console.error('Error Object:', errorObj)
      }
    } else if (error !== null && error !== undefined) {
      console.error('Raw Error:', error)
    }
    
    console.groupEnd()

      return errorInfo
    } catch (logError) {
      // Fallback if error logging itself fails - try to extract as much info as possible
      console.error('Failed to log error:', logError)
      
      // Try to extract basic info from the original error
      let fallbackMessage = 'Error logging failed'
      let fallbackEndpoint = context || 'Unknown'
      
      try {
        if (error && typeof error === 'object') {
          const err = error as any
          if (err.message) fallbackMessage = `Error: ${err.message}`
          else if (err.error) fallbackMessage = `Error: ${err.error}`
          else if (err.detail) fallbackMessage = `Error: ${err.detail}`
        } else if (error) {
          fallbackMessage = `Error: ${String(error)}`
        }
        
        if (axios.isAxiosError(error)) {
          fallbackEndpoint = error.config?.url || context || 'Unknown'
          if (error.response?.status) {
            fallbackMessage = `HTTP ${error.response.status}: ${fallbackMessage}`
          }
        }
      } catch (extractError) {
        // If we can't extract info, use defaults
      }
      
      // Log the original error as best we can
      try {
        console.error('Original error (fallback):', {
          message: fallbackMessage,
          endpoint: fallbackEndpoint,
          errorType: error instanceof Error ? error.constructor.name : typeof error,
          hasResponse: axios.isAxiosError(error) ? !!error.response : false,
          status: axios.isAxiosError(error) && error.response ? error.response.status : undefined
        })
      } catch (e) {
        console.error('Could not log original error details')
      }
      
      return {
        message: fallbackMessage,
        timestamp: new Date().toISOString(),
        endpoint: fallbackEndpoint,
        errorType: 'LoggingError',
        details: {
          loggingError: String(logError),
          originalErrorType: error instanceof Error ? error.constructor.name : typeof error
        }
      }
    }
  }

  static createErrorHandler(endpoint: string) {
    return (error: AxiosError | Error | unknown) => {
      try {
        const errorInfo = this.logError(error, endpoint)
        
        // Provide user-friendly error messages
        if (axios.isAxiosError(error)) {
          if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
            throw new Error(`Request to ${endpoint} timed out. The server may be slow or unresponsive.`)
          } else if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error')) {
            throw new Error(`Cannot connect to backend server at ${API_URL}. Please ensure the backend is running.`)
          } else if (error.response) {
            const status = error.response.status
            let data: any = {}
            try {
              data = error.response.data || {}
            } catch (e) {
              // If we can't parse response data, use defaults
            }
            
            if (status === 404) {
              throw new Error(`Resource not found: ${endpoint}`)
            } else if (status === 403) {
              throw new Error(`Access denied: ${endpoint}`)
            } else if (status === 500) {
              const errorMsg = data?.error_message || data?.detail || data?.message || 'Internal server error'
              throw new Error(`Server error: ${errorMsg}`)
            } else {
              const errorMsg = data?.error_message || data?.detail || data?.message || error.response.statusText || 'Unknown error'
              throw new Error(`API error (${status}): ${errorMsg}`)
            }
          }
        }
        
        // If it's not an Axios error, just throw the original
        throw error
      } catch (handlerError) {
        // If error handler itself fails, throw original error
        if (handlerError === error) {
          throw handlerError
        }
        // Otherwise, throw the processed error
        throw handlerError
      }
    }
  }
}

// Axios interceptor for request logging
axios.interceptors.request.use(
  (config) => {
    const startTime = performance.now()
    config.metadata = { startTime }
    ApiDebugger.logRequest(config)
    return config
  },
  (error) => {
    ApiDebugger.logError(error, 'Request Interceptor')
    return Promise.reject(error)
  }
)

// Axios interceptor for response logging
axios.interceptors.response.use(
  (response) => {
    const endTime = performance.now()
    const duration = endTime - (response.config.metadata?.startTime || endTime)
    response.config.metadata = { ...response.config.metadata, duration }
    ApiDebugger.logResponse(response)
    return response
  },
  (error) => {
    ApiDebugger.logError(error, 'Response Interceptor')
    return Promise.reject(error)
  }
)

// Enable debugging in development
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
  ApiDebugger.enable()
  console.log('[API Debug] Enabled - API calls will be logged to console')
  console.log('[API Debug] To disable: localStorage.setItem("api_debug", "false")')
}

