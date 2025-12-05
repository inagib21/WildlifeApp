# Wildlife App API Endpoints Documentation

This document explains all 67 API endpoints in the Wildlife Detection System.

## 📋 Table of Contents
1. [Root & System Health](#root--system-health)
2. [Camera Management](#camera-management)
3. [Detection Management](#detection-management)
4. [Image Processing](#image-processing)
5. [Analytics & Statistics](#analytics--statistics)
6. [Real-time Events (SSE)](#real-time-events-sse)
7. [Media Serving](#media-serving)
8. [Webhooks](#webhooks)
9. [Backups](#backups)
10. [Authentication](#authentication)
11. [Configuration](#configuration)
12. [Notifications](#notifications)
13. [Audit Logs](#audit-logs)
14. [Debug & Maintenance](#debug--maintenance)
15. [Thingino Camera Integration](#thingino-camera-integration)

---

## 🔍 Root & System Health

### `GET /`
**Purpose**: Basic API information  
**What it does**: Returns a simple message confirming the API is running  
**Response**: `{"message": "Wildlife Monitoring API with SpeciesNet Integration"}`

### `GET /system`
**Purpose**: Get system health status (cached, fast response)  
**What it does**: 
- Returns CPU, memory, disk usage
- Checks MotionEye and SpeciesNet service status
- Calculates media directory sizes
- Cached for 10 seconds for performance
- Returns quickly even if services are slow (uses timeouts)

### `GET /api/system`
**Purpose**: Alias for `/system` (for frontend compatibility)

### `GET /health`
**Purpose**: Basic health check for monitoring tools  
**What it does**: Quick check that returns 200 if system is running  
**Response**: `{"status": "healthy", "timestamp": "...", "message": "Backend is running"}`

### `GET /api/health`
**Purpose**: Alias for `/health`

### `GET /health/detailed`
**Purpose**: Comprehensive health check with metrics  
**What it does**:
- Database connectivity test
- MotionEye service check (with timeout)
- SpeciesNet service check (with timeout)
- System resources (CPU, memory, disk)
- Database statistics (detection count, camera count)
- Returns 503 if unhealthy, 200 if healthy

---

## 📹 Camera Management

### `GET /cameras`
**Purpose**: Get list of all cameras with statistics  
**What it does**:
- Fetches all cameras from database
- Pre-fetches detection counts for all cameras (avoids N+1 queries)
- Gets last detection timestamp per camera
- Validates and normalizes camera data
- Adds stream URLs from MotionEye
- Cached for 60 seconds
**Response**: List of cameras with detection counts, last detection time, status

### `GET /api/cameras`
**Purpose**: Alias for `/cameras` (for frontend)

### `POST /cameras/sync`
**Purpose**: Sync cameras from MotionEye to database  
**What it does**:
- Connects to MotionEye service
- Fetches all cameras from MotionEye
- Creates new cameras in database if they don't exist
- Updates existing cameras with current MotionEye settings
- Removes cameras that no longer exist in MotionEye
- Logs sync results in audit log
**Rate Limit**: 10/minute (expensive operation)

### `POST /cameras`
**Purpose**: Add a new camera  
**What it does**:
- Creates camera in database
- Adds camera to MotionEye configuration
- If MotionEye fails, rolls back database changes
- Generates stream URLs
- Logs creation in audit log
**Rate Limit**: 20/minute

### `GET /cameras/{camera_id}`
**Purpose**: Get details for a specific camera  
**What it does**: Returns full camera information including settings

### `GET /cameras/{camera_id}/motion-settings`
**Purpose**: Get motion detection settings for a camera  
**What it does**: Returns motion detection configuration (threshold, smart mask, etc.)

### `POST /cameras/{camera_id}/motion-settings`
**Purpose**: Update motion detection settings  
**What it does**: Updates motion detection parameters for a camera

### `GET /stream/{camera_id}`
**Purpose**: Get camera stream information  
**What it does**: Returns RTSP URL, stream URL, MJPEG URL, and MotionEye URL for a camera

---

## 🦌 Detection Management

### `GET /detections`
**Purpose**: Get detections with filtering and pagination  
**What it does**:
- Supports filtering by: camera_id, species, date range, search term
- Search searches across species, image_path, and camera names
- Pagination with limit (default 50) and offset
- Batch-fetches cameras to avoid N+1 queries
- Generates media URLs from image paths
- Validates and normalizes detection data
- Handles both motioneye_media and archived_photos paths
**Query Parameters**: camera_id, limit, offset, species, start_date, end_date, search

### `GET /api/detections`
**Purpose**: Alias for `/detections`

### `POST /detections`
**Purpose**: Create a new detection manually  
**What it does**: Adds a detection record to the database (for manual entry)

### `DELETE /detections/{detection_id}`
**Purpose**: Delete a single detection  
**What it does**: Removes detection from database, logs deletion

### `POST /detections/bulk-delete`
**Purpose**: Delete multiple detections at once  
**What it does**: Accepts list of detection IDs and deletes them all

### `GET /detections/count`
**Purpose**: Get total count of detections  
**What it does**: Returns total count, optionally filtered by camera_id

### `GET /api/detections/count`
**Purpose**: Alias for `/detections/count`

### `GET /api/detections/export`
**Purpose**: Export detections to CSV, JSON, or PDF  
**What it does**:
- Supports filtering (camera_id, species, date range)
- CSV: Generates comma-separated file
- JSON: Returns JSON array
- PDF: Creates formatted report with ReportLab
- Logs export in audit log
**Rate Limit**: 10/minute (expensive operation)

---

## 🖼️ Image Processing

### `POST /process-image`
**Purpose**: Process an uploaded image with SpeciesNet  
**What it does**:
- Accepts image file upload
- Processes image through SpeciesNet AI model
- Creates detection record in database
- Optionally compresses image
- Supports async mode (returns task ID immediately)
- Logs processing in audit log
**Rate Limit**: 10/minute (expensive operation)

### `POST /api/motioneye/webhook`
**Purpose**: Receive motion detection events from MotionEye  
**What it does**:
- Receives webhook when MotionEye detects motion
- Parses MotionEye payload
- Maps file paths from Docker container to local paths
- Skips duplicate events (using event cache)
- Skips motion mask files (debug images)
- Processes image with SpeciesNet
- Uses Smart Detection processor for enhanced analysis
- Creates detection record
- Sends notifications if high confidence
- Triggers webhooks for detection events
- Broadcasts detection to real-time clients
- Archives photos by species
**This is the main entry point for automatic detections!**

---

## 📊 Analytics & Statistics

### `GET /detections/species-counts`
**Purpose**: Get species detection counts  
**What it does**: Returns top 10 species by count for week/month/all time  
**Query Parameters**: range (week/month/all)

### `GET /detections/unique-species-count`
**Purpose**: Count unique species detected  
**What it does**: Returns number of distinct species in last N days  
**Query Parameters**: days (default 30)

### `GET /api/analytics/species`
**Purpose**: Detailed species analytics  
**What it does**:
- Groups detections by species
- Calculates average confidence per species
- Returns detection count per species
- Supports date range and camera filtering
- Includes top 10 most recent detections per species
**Rate Limit**: 60/minute

### `GET /api/analytics/timeline`
**Purpose**: Detection timeline analytics  
**What it does**:
- Groups detections by time interval (day/week/month)
- Returns detection counts per interval
- Includes species breakdown per interval
- Supports date range and camera filtering
**Query Parameters**: interval (day/week/month), start_date, end_date, camera_id

### `GET /api/analytics/cameras`
**Purpose**: Camera-specific analytics  
**What it does**:
- Groups detections by camera
- Calculates average confidence per camera
- Returns top 5 species per camera
- Supports date range filtering
**Rate Limit**: 60/minute

### `GET /analytics/detections/timeseries`
**Purpose**: Time series data for detections  
**What it does**: Returns detection counts grouped by hour or day  
**Query Parameters**: interval (hour/day), days (default 7)

### `GET /analytics/detections/top_species`
**Purpose**: Top N species by detection count  
**What it does**: Returns most detected species in last N days  
**Query Parameters**: limit (default 5), days (default 30)

### `GET /analytics/detections/unique_species_count`
**Purpose**: Count unique species (SQL version)  
**What it does**: Same as `/detections/unique-species-count` but uses raw SQL

---

## 🔴 Real-time Events (SSE)

### `GET /events/detections`
**Purpose**: Server-Sent Events stream for real-time detection updates  
**What it does**:
- Establishes SSE connection
- Sends new detections as they occur
- Sends keepalive messages every 30 seconds
- Automatically cleans up on disconnect
**Use Case**: Frontend dashboard showing detections in real-time

### `GET /events/system`
**Purpose**: Server-Sent Events stream for system updates  
**What it does**:
- Establishes SSE connection
- Sends periodic system health updates (every 30 seconds)
- Includes CPU, memory, disk, MotionEye status, SpeciesNet status
**Use Case**: Real-time system monitoring dashboard

---

## 🎬 Media Serving

### `GET /media/{camera}/{date}/{filename}`
**Purpose**: Serve media files from motioneye_media or archived_photos  
**What it does**:
- Searches in motioneye_media first
- Falls back to archived_photos (searches all species folders)
- Returns image file with proper content type
- Handles both Camera1 and numeric camera IDs

### `GET /archived_photos/{species}/{camera}/{date}/{filename}`
**Purpose**: Serve archived photos directly  
**What it does**: Returns archived photo file organized by species

### `GET /thumbnails/{filename}`
**Purpose**: Serve thumbnail images  
**What it does**: Returns compressed thumbnail from cache

---

## 🔗 Webhooks

### `POST /api/webhooks`
**Purpose**: Create a new webhook  
**What it does**: Creates webhook configuration that will be triggered on detection events  
**Rate Limit**: 10/hour

### `GET /api/webhooks`
**Purpose**: List all webhooks  
**What it does**: Returns all webhooks, optionally filtered by is_active or event_type  
**Rate Limit**: 60/minute

### `GET /api/webhooks/{webhook_id}`
**Purpose**: Get specific webhook details  
**What it does**: Returns webhook configuration

### `PUT /api/webhooks/{webhook_id}`
**Purpose**: Update a webhook  
**What it does**: Updates webhook configuration  
**Rate Limit**: 10/hour

### `DELETE /api/webhooks/{webhook_id}`
**Purpose**: Delete a webhook  
**What it does**: Removes webhook configuration  
**Rate Limit**: 10/hour

### `POST /api/webhooks/{webhook_id}/test`
**Purpose**: Test a webhook  
**What it does**: Sends a test payload to the webhook URL to verify it works  
**Rate Limit**: 10/hour

---

## 💾 Backups

### `POST /api/backup/create`
**Purpose**: Manually create a database backup  
**What it does**: Creates a timestamped SQLite backup file  
**Rate Limit**: 5/hour

### `GET /api/backup/list`
**Purpose**: List all available backups  
**What it does**: Returns list of backup files with size and timestamp  
**Rate Limit**: 60/minute

### `POST /api/backup/cleanup`
**Purpose**: Clean up old backups  
**What it does**: Deletes old backups, keeping only the most recent N  
**Query Parameters**: keep_count (default 10)  
**Rate Limit**: 5/hour

---

## 🔐 Authentication

### `POST /api/auth/register`
**Purpose**: Register a new user  
**What it does**:
- Creates user account
- Hashes password
- Assigns role (viewer/editor/admin)
- Logs registration in audit log
**Rate Limit**: 5/hour

### `POST /api/auth/login`
**Purpose**: Login and create session  
**What it does**:
- Validates username/password
- Creates session token
- Records login IP and user agent
- Returns user info and token
- Logs login in audit log
**Rate Limit**: 10/minute

### `POST /api/auth/logout`
**Purpose**: Logout and invalidate session  
**What it does**: Invalidates session token, logs logout  
**Rate Limit**: 30/hour

### `GET /api/auth/me`
**Purpose**: Get current user information  
**What it does**: Returns user info from session token  
**Rate Limit**: 60/minute

### `POST /api/auth/change-password`
**Purpose**: Change user password  
**What it does**: Validates old password, sets new password, logs change  
**Rate Limit**: 10/hour

---

## ⚙️ Configuration

### `GET /api/config`
**Purpose**: Get current configuration values  
**What it does**: Returns configuration (masks sensitive data like passwords)  
**Note**: Read-only, changes require .env file modification  
**Rate Limit**: 60/minute

### `POST /api/config`
**Purpose**: Update configuration (UI only, doesn't actually change config)  
**What it does**: Logs the attempt, but returns message that .env file must be edited  
**Rate Limit**: 10/hour

---

## 🔔 Notifications

### `GET /api/notifications/status`
**Purpose**: Get notification enabled status  
**What it does**: Returns whether notifications are enabled

### `POST /api/notifications/toggle`
**Purpose**: Toggle notifications on/off  
**What it does**: Switches notification state, logs change  
**Rate Limit**: 10/minute

### `PUT /api/notifications/enabled`
**Purpose**: Set notification enabled state  
**What it does**: Sets notification state to true/false, logs change  
**Rate Limit**: 10/minute

---

## 📝 Audit Logs

### `GET /audit-logs`
**Purpose**: Get audit logs with filtering  
**What it does**:
- Returns audit log entries
- Supports filtering by: action, resource_type, resource_id, success_only
- Defaults to last 30 days
- Pagination with limit/offset
**Rate Limit**: 60/minute

### `GET /api/audit-logs`
**Purpose**: Alias for `/audit-logs`

---

## 🐛 Debug & Maintenance

### `GET /api/debug/speciesnet-response/{detection_id}`
**Purpose**: View raw SpeciesNet response for a detection  
**What it does**: Returns the original JSON response from SpeciesNet AI model  
**Use Case**: Debugging why a species was identified incorrectly

### `GET /api/debug/detection-media/{detection_id}`
**Purpose**: Debug media URL generation  
**What it does**: Shows how media URL was generated from image_path  
**Use Case**: Troubleshooting broken image links

### `GET /api/debug/file-system`
**Purpose**: Check file system structure  
**What it does**: Returns directory structure of archived_photos and motioneye_media  
**Use Case**: Verifying files are organized correctly

### `GET /api/trigger-photo-scan`
**Purpose**: Manually trigger photo scanner  
**What it does**: Scans motioneye_media for unprocessed photos and processes them  
**Use Case**: Processing old photos that weren't detected automatically

### `GET /api/photo-scan-status`
**Purpose**: Get photo scanner status  
**What it does**: Returns statistics about processed/unprocessed photos  
**Response**: total_photos, processed_photos, unprocessed_photos, scanner_active

---

## 📱 Thingino Camera Integration

### `POST /api/thingino/capture`
**Purpose**: Capture image from Thingino camera  
**What it does**: 
- Connects to Thingino camera via HTTP
- Captures current image
- Processes with SpeciesNet
- Creates detection record
**Use Case**: Manual capture from Thingino cameras

### `GET /api/thingino/image/{detection_id}`
**Purpose**: Get image from Thingino detection  
**What it does**: Returns image data from Thingino camera detection

### `POST /api/thingino/webhook`
**Purpose**: Receive webhook from Thingino camera  
**What it does**: Processes motion detection events from Thingino cameras

---

## 🔄 How It All Works Together

### Detection Flow:
1. **MotionEye detects motion** → Sends webhook to `/api/motioneye/webhook`
2. **Backend processes image** → Uses SpeciesNet AI to identify species
3. **Smart Detection analyzes** → Filters low-quality detections
4. **Detection saved** → Stored in database with metadata
5. **Notifications sent** → If confidence is high enough
6. **Webhooks triggered** → External systems notified
7. **Real-time broadcast** → Frontend receives update via SSE
8. **Photo archived** → Organized by species in archived_photos

### Frontend Integration:
- Frontend polls `/api/system` for health status
- Frontend connects to `/events/detections` for real-time updates
- Frontend queries `/api/detections` with filters for list view
- Frontend uses `/api/analytics/*` for charts and statistics
- Frontend displays images via `/media/*` endpoints

---

## 📈 Rate Limits

Most endpoints have rate limiting to prevent abuse:
- **High-frequency endpoints**: 60-120 requests/minute (health checks, lists)
- **Medium-frequency endpoints**: 10-20 requests/minute (creates, updates)
- **Expensive operations**: 5-10 requests/hour (backups, exports, webhooks)

---

## 🔒 Security

- API key authentication (optional, configurable)
- CORS middleware restricts origins
- Rate limiting prevents abuse
- Audit logging tracks all actions
- Session-based authentication for user accounts
- Password hashing for user accounts

---

*Last updated: After code cleanup and compression*

