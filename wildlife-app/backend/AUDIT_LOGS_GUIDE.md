# Audit Logs Guide

## What Are Audit Logs?

Audit logs provide a complete history of all system changes and activities. They track **who** made changes, **what** changed, **when** it happened, and **whether** it succeeded or failed. This is essential for:

- **Security**: Track who accessed the system and what they did
- **Accountability**: Know exactly who made which changes
- **Debugging**: Trace issues back to specific actions
- **Compliance**: Maintain a complete audit trail
- **Monitoring**: Understand system usage patterns

## What Information Do Audit Logs Track?

### 1. **Who Made Changes**
- **IP Address**: The IP address of the user/client making the change
- **User Agent**: Browser or client application used
- **Endpoint**: Which API endpoint was called

**Use Cases:**
- Identify unauthorized access attempts
- Track which users/devices made changes
- Investigate suspicious activity
- Monitor access patterns

### 2. **What Changed**
- **Action Type**: 
  - `CREATE` - New cameras or detections created
  - `UPDATE` - Settings or configurations changed
  - `DELETE` - Resources removed
  - `SYNC` - Cameras synced from MotionEye
  - `WEBHOOK` - Webhook events received (Thingino, MotionEye)
  - `CAPTURE` - Camera captures triggered
  - `PROCESS` - Images processed with SpeciesNet
  - `TRIGGER` - System operations triggered (photo scans, etc.)
- **Resource Type**: What was affected (camera, detection, motion_settings, photo_scan)
- **Resource ID**: The specific item that changed (e.g., camera #5, detection #1234)

**Use Cases:**
- See what operations occurred in the system
- Track changes to specific cameras
- Monitor detection processing activity
- Review configuration changes

### 3. **When It Happened**
- **Timestamp**: Exact time (UTC) when each action occurred

**Use Cases:**
- Create a timeline of events
- Correlate changes with system issues
- Track activity patterns over time
- Investigate incidents with precise timing

### 4. **Success or Failure**
- **Success Status**: Whether the action succeeded (✓) or failed (✗)
- **Error Messages**: Detailed error information if the action failed

**Use Cases:**
- Identify failed operations quickly
- Debug system issues
- Monitor system health
- Track error rates

### 5. **Detailed Context**
- **Details (JSON)**: Additional context including:
  - Camera names, URLs, and configurations
  - Species detected with confidence scores
  - Settings that were changed
  - Sync statistics (how many cameras synced/updated/removed)
  - And much more...

**Use Cases:**
- See exactly what changed in detail
- Understand the full context of an action
- Debug specific issues with complete information

## Real-World Examples

### Example 1: Camera Added
```
Action: CREATE
Resource: camera #5
IP: 192.168.1.100
Details: {"camera_name": "Front Yard Camera", "url": "rtsp://..."}
Success: ✓
```
**Tells you:** Someone added a new camera, exactly when, and from which IP address.

### Example 2: Detection Processed
```
Action: PROCESS
Resource: detection #1234
IP: 127.0.0.1 (webhook)
Details: {"camera_id": 3, "species": "Deer", "confidence": 0.95}
Success: ✓
```
**Tells you:** A detection was processed, which camera it came from, what species was detected, and the confidence level.

### Example 3: Failed Sync
```
Action: SYNC
Resource: camera
IP: 192.168.1.50
Error: "Connection timeout to MotionEye"
Success: ✗
```
**Tells you:** A camera sync failed, when it happened, from which IP, and why it failed.

### Example 4: Settings Changed
```
Action: UPDATE
Resource: motion_settings #2
IP: 192.168.1.100
Details: {"threshold": 2000, "smart_mask_speed": 15}
Success: ✓
```
**Tells you:** Motion detection settings were changed, what specifically changed, and who made the change.

## Questions You Can Answer

With audit logs, you can answer questions like:

- ✅ **Who** added or modified cameras?
- ✅ **When** was a specific detection processed?
- ✅ **Why** did a sync operation fail?
- ✅ **What** settings were changed and when?
- ✅ **Which** IP addresses are making changes to the system?
- ✅ **How many** operations succeeded vs failed?
- ✅ **What** was the sequence of events leading to an issue?

## How to Access Audit Logs

### Method 1: Frontend UI (Recommended)

1. Start the application:
   ```bash
   # Use the startup script
   scripts/wildlife-app-control.bat
   # Select option 1 to start all services
   ```

2. Open your browser and navigate to:
   - `http://localhost:3000/audit-logs`
   - Or click "Audit Logs" in the left sidebar navigation

3. Use the filters:
   - **Action**: Filter by action type (CREATE, UPDATE, DELETE, SYNC, WEBHOOK, etc.)
   - **Resource Type**: Filter by resource type (camera, detection, motion_settings, etc.)
   - **Limit**: Number of logs to display (default: 100, max: 500)
   - **Success Only**: Show only successful actions

### Method 2: API Endpoint

#### Get All Audit Logs (Last 30 Days)
```bash
GET http://localhost:8001/api/audit-logs
```

#### Get Audit Logs with Filters
```bash
# Filter by action
GET http://localhost:8001/api/audit-logs?action=CREATE

# Filter by resource type
GET http://localhost:8001/api/audit-logs?resource_type=camera

# Filter by resource ID
GET http://localhost:8001/api/audit-logs?resource_id=5

# Show only successful actions
GET http://localhost:8001/api/audit-logs?success_only=true

# Limit results
GET http://localhost:8001/api/audit-logs?limit=50&offset=0

# Combine filters
GET http://localhost:8001/api/audit-logs?action=CREATE&resource_type=camera&limit=20
```

#### Using curl
```bash
# Get all logs
curl http://localhost:8001/api/audit-logs

# Get logs for camera operations only
curl "http://localhost:8001/api/audit-logs?resource_type=camera"

# Get failed operations
curl "http://localhost:8001/api/audit-logs?success_only=false"
```

#### Using PowerShell
```powershell
# Get all logs
Invoke-WebRequest -Uri "http://localhost:8001/api/audit-logs" -UseBasicParsing | Select-Object -ExpandProperty Content | ConvertFrom-Json

# Get logs with filters
Invoke-WebRequest -Uri "http://localhost:8001/api/audit-logs?action=CREATE&limit=10" -UseBasicParsing | Select-Object -ExpandProperty Content | ConvertFrom-Json
```

## What Gets Logged

The audit system automatically logs:

- **Camera Operations**:
  - Camera sync from MotionEye
  - Camera creation
  - Camera updates

- **Detection Operations**:
  - Detection creation
  - Image processing with SpeciesNet
  - Camera captures (Thingino)
  - Webhook detections (Thingino and MotionEye)

- **Settings Operations**:
  - Motion detection settings updates

- **System Operations**:
  - Photo scan triggers

## Log Fields

Each audit log entry contains:

- `id`: Unique log entry ID
- `timestamp`: When the action occurred (UTC)
- `action`: Action type (CREATE, UPDATE, DELETE, SYNC, WEBHOOK, CAPTURE, PROCESS, TRIGGER)
- `resource_type`: Type of resource (camera, detection, motion_settings, photo_scan)
- `resource_id`: ID of the affected resource (if applicable)
- `user_ip`: IP address of the user/client making the change
- `user_agent`: Browser/client user agent string
- `endpoint`: API endpoint that was called
- `details`: JSON string with additional context (expandable in UI)
- `success`: Whether the action succeeded (true/false)
- `error_message`: Error message if the action failed

## Example Response

```json
[
  {
    "id": 1,
    "timestamp": "2025-11-21T21:30:00.000000",
    "action": "CREATE",
    "resource_type": "camera",
    "resource_id": 5,
    "user_ip": "127.0.0.1",
    "user_agent": "Mozilla/5.0...",
    "endpoint": "/cameras",
    "details": "{\"camera_name\": \"Front Yard Camera\", \"url\": \"rtsp://...\"}",
    "success": true,
    "error_message": null
  }
]
```

## Rate Limiting

The audit logs endpoint is rate-limited to **60 requests per minute** to prevent abuse.

## Security and Compliance Benefits

The audit logging system provides:

1. **Accountability**: Every change is tracked with who made it
2. **Security**: Detect unauthorized access or suspicious activity
3. **Compliance**: Maintain complete audit trails for regulatory requirements
4. **Debugging**: Trace issues back to specific actions and timestamps
5. **Monitoring**: Track system usage patterns and identify trends

## Notes

- Audit logs are stored in the PostgreSQL database in the `audit_logs` table
- Logs are automatically created for all write operations
- The frontend auto-refreshes every 30 seconds
- Failed operations are also logged with error messages
- IP addresses are captured for security and compliance purposes
- All logs include timestamps in UTC for consistency
- The system tracks both successful and failed operations
- Detailed JSON context is stored for each action

