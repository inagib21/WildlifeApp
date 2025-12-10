# Webhook Improvements Summary

## Issues Investigated

### 1. Empty Webhook Payload Errors
**Problem**: Multiple webhooks were failing with "Empty webhook payload" errors.

**Root Causes Identified**:
- Webhook script may be called with empty arguments
- JSON payload might be malformed if variables are empty
- Request body parsing might fail silently

## Improvements Made

### 1. Enhanced Webhook Error Handling (`routers/webhooks.py`)
- Added detailed logging for empty request bodies
- Improved error messages with request details (content-type, headers, URL)
- Better error categorization and diagnostics
- Added raw payload logging for debugging

### 2. Improved Webhook Parsing (`motioneye_webhook.py`)
- Added error handling for each parser attempt
- Better logging of parser failures
- More robust handling of different payload formats

### 3. Enhanced Webhook Script (`motioneye_config/send_webhook.sh`)
- Added validation for required parameters (CAMERA_ID, FILE_PATH)
- Script now exits early if required parameters are missing
- Added JSON escaping to prevent injection issues
- Improved error logging with all arguments

### 4. New Diagnostic Endpoint (`/api/webhooks/diagnostics`)
- Provides real-time webhook activity statistics
- Shows recent webhook logs with success/failure status
- Displays recent detections
- Shows system configuration (camera count, webhook URL, script path)

## Usage

### Check Webhook Diagnostics
```bash
curl http://localhost:8001/api/webhooks/diagnostics
```

### Check Recent Activity
```bash
cd wildlife-app/backend
python check_detections_status.py
```

## Next Steps

1. **Monitor webhook activity** using the new diagnostic endpoint
2. **Check MotionEye logs** if empty payloads continue:
   ```bash
   docker logs wildlife-motioneye | grep webhook
   ```
3. **Verify webhook script is executable** in MotionEye container:
   ```bash
   docker exec wildlife-motioneye ls -la /etc/motioneye/send_webhook.sh
   ```
4. **Check webhook debug log** inside MotionEye container:
   ```bash
   docker exec wildlife-motioneye cat /tmp/webhook_debug.log
   ```

## Configuration Verification

All cameras should have webhook configured in their config files:
- `on_picture_save /etc/motioneye/send_webhook.sh %$ %f picture_save %t`
- `on_movie_end /etc/motioneye/send_webhook.sh %$ %f movie_end %t`

The webhook script sends to: `http://host.docker.internal:8001/api/motioneye/webhook`

