# Camera Detection Troubleshooting Guide

If only some cameras are detecting, follow these steps:

## Quick Diagnosis

1. **Check Backend Logs**: Look for webhook messages like:
   ```
   MotionEye webhook received - camera_id: X, file_path: ...
   📹 Webhook from CameraName (ID: X) - Event: ...
   ```

2. **Run Diagnostic Script**:
   ```bash
   cd wildlife-app/backend
   python scripts/check_camera_webhooks.py
   ```

## Common Issues

### Issue 1: Motion Detection Disabled
**Symptom**: Camera config shows `motion_detection on` but no detections

**Solution**: 
- Open MotionEye UI: http://localhost:8765
- Go to each camera's settings
- Ensure "Motion Detection" is enabled
- Check "Save Pictures" is set to "On Motion" or "Always"

### Issue 2: Threshold Too High
**Symptom**: Camera has very high threshold (e.g., 45000+) and doesn't detect motion

**Solution**:
- Lower the threshold in MotionEye camera settings
- Recommended: Start with 1500-5000 and adjust based on environment
- Use "Threshold Tune" feature in MotionEye to find optimal value

### Issue 3: Picture Output Settings
**Symptom**: `picture_output_motion off` in config

**Solution**:
- In MotionEye UI, set "Save Pictures" to "On Motion" or "Always"
- This ensures `picture_output_motion on` in config
- Webhook fires on `on_picture_save` which requires pictures to be saved

### Issue 4: Camera Not Connected
**Symptom**: Camera shows as offline or stream not working

**Solution**:
- Check camera RTSP URL is correct
- Verify camera is powered on and connected to network
- Test RTSP stream directly: `ffplay rtsp://192.168.88.XXX:554/ch0`
- Check camera credentials in MotionEye config

### Issue 5: Webhook Not Reaching Backend
**Symptom**: No webhook logs in backend for specific cameras

**Solution**:
- Verify webhook URL in MotionEye config: `http://localhost:8001/api/motioneye/webhook`
- Check backend is running on port 8001
- Check MotionEye can reach backend (if in Docker, use `host.docker.internal:8001` or Docker network)
- Restart MotionEye container to reload configs

### Issue 6: Camera ID Mismatch
**Symptom**: Webhooks received but camera_id doesn't match database

**Solution**:
- Run camera sync: `POST /api/cameras/sync`
- Verify camera IDs in database match MotionEye camera IDs
- Check MotionEye camera numbering (starts at 1, not 0)

## Current Camera Config Analysis

Based on config files:

| Camera | Motion Detection | Picture Output Motion | Threshold | Status |
|--------|-----------------|----------------------|-----------|--------|
| Camera 1 | ✅ On | ✅ On | 45465 | Should detect |
| Camera 2 | ✅ On | ❌ Off | 46080 | May not detect (needs manual snapshots) |
| Camera 3 | ✅ On | ❌ Off | 45772 | May not detect (needs manual snapshots) |
| Camera 4 | ✅ On | ✅ On | 46694 | Should detect |
| Camera 5 | ✅ On | ✅ On | 45772 | Should detect |
| Camera 6 | ✅ On | ✅ On | 46080 | Should detect |
| Camera 8 | ✅ On | ✅ On | ? | Should detect |

**Key Finding**: Cameras 2 and 3 have `picture_output_motion off`, which means they only save pictures on manual snapshots, not on motion detection. This is likely why they're not detecting!

## Fix for Cameras 2 and 3

1. **Via MotionEye UI** (Recommended):
   - Open http://localhost:8765
   - Go to Camera 2 settings
   - Set "Save Pictures" to "On Motion" or "Always"
   - Repeat for Camera 3
   - Save settings

2. **Via Config File** (Advanced):
   - Edit `motioneye_config/camera-2.conf`
   - Change `picture_output_motion off` to `picture_output_motion on`
   - Edit `motioneye_config/camera-3.conf`
   - Change `picture_output_motion off` to `picture_output_motion on`
   - Restart MotionEye container

## Verification Steps

1. **Check Backend Logs**:
   ```bash
   # Look for webhook messages from all cameras
   grep "MotionEye webhook received" backend/logs/*.log
   ```

2. **Check Recent Detections**:
   ```bash
   # Query database for detections by camera
   # Or use frontend: Filter detections by camera
   ```

3. **Test Webhook Manually**:
   ```bash
   # Trigger a manual snapshot in MotionEye for each camera
   # Check if webhook is received in backend logs
   ```

## Expected Behavior

- **All cameras** should send webhooks when motion is detected
- **Webhook logs** should appear in backend for each camera
- **Detections** should be created in database for each webhook
- **Smart detection** should process each image

## Still Not Working?

1. Check MotionEye container logs: `docker logs <motioneye-container>`
2. Check backend logs for errors
3. Verify camera streams are working in MotionEye UI
4. Test webhook endpoint manually: `curl -X POST http://localhost:8001/api/motioneye/webhook`
5. Check network connectivity between MotionEye and backend

