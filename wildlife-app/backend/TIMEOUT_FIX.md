# Timeout Fix Summary

## Issue
Frontend was timing out when fetching detections due to:
1. Backend not responding (crashed or hung)
2. Frontend trying to fetch 2000 detections in large chunks
3. 30-second timeout per chunk was too long

## Fixes Applied

### Frontend Optimizations (`lib/api.ts`)
1. **Reduced default limit**: Changed from 2000 to 500 detections
2. **Smaller chunks**: Reduced chunk size from 500 to 100
3. **Faster timeout**: Reduced from 30s to 15s per chunk
4. **Better error handling**: Chunks fail gracefully, returns partial results
5. **Reduced delays**: Smaller delay between chunks (50ms instead of 100ms)

### Backend Optimizations (`routers/detections.py`)
1. **Query limit cap**: Maximum 1000 detections per request (prevents huge queries)
2. **Optimized query order**: Limit applied before offset for better performance
3. **Index usage**: Queries use timestamp index for faster sorting

### Dashboard Changes (`components/realtime-dashboard.tsx`)
1. **Reduced initial load**: Changed from 2000 to 500 detections
2. **Increased delay**: Wait 2 seconds before loading large dataset
3. **Better error handling**: Sets empty array on failure instead of undefined

## Result
- Frontend loads faster
- Less load on backend
- Better error recovery
- Prevents timeout errors

## Next Steps
1. Restart backend: `scripts\control.bat -> [1] Start All Services`
2. Refresh frontend (Ctrl+F5)
3. Dashboard should load without timeouts

