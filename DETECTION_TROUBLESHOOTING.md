# Detection Not Appearing - Troubleshooting Guide

## Issue: Person walked past camera but no detection appeared

### What We Found:
1. ✅ MotionEye IS detecting motion and saving pictures
2. ✅ Webhook script IS being called (check `/tmp/webhook_debug.log`)
3. ✅ Backend IS reachable from MotionEye container
4. ⚠️ Webhook curl might be failing silently

### Quick Checks:

1. **Check webhook debug log in MotionEye**:
   ```bash
   docker exec wildlife-motioneye tail -20 /tmp/webhook_debug.log
   ```
   Look for "Webhook sent successfully" or "Webhook FAILED" messages

2. **Check backend logs** for webhook receipts:
   - Look for "MotionEye webhook received" messages
   - Check for errors or warnings

3. **Check recent detections**:
   - Frontend: http://localhost:3000/detections
   - Filter by time (last 15 minutes)
   - Check if detections are being saved but filtered out

### Common Issues:

#### Issue 1: Webhook Script Not Reaching Backend
**Symptom**: Webhook script is called but backend doesn't receive it

**Solution**: 
- The webhook script has been updated to log HTTP response codes
- Check `/tmp/webhook_debug.log` for "Webhook FAILED" messages
- Verify backend is running: `curl http://localhost:8001/health`

#### Issue 2: Low Confidence Filtering
**Symptom**: Webhooks received but detections not saved

**Solution**:
- Minimum confidence threshold is 0.15
- If SpeciesNet returns low confidence (< 0.15), detection won't be saved
- Check backend logs for "Skipping detection save: confidence too low" messages

#### Issue 3: Motion Mask Files Being Skipped
**Symptom**: Many webhooks but no detections

**Solution**:
- Files ending in "m.jpg" or "m.jpeg" are motion mask files (skipped)
- Only regular image files are processed
- This is normal - check for files WITHOUT "m" suffix

#### Issue 4: File Not Found
**Symptom**: Webhook received but file doesn't exist locally

**Solution**:
- MotionEye saves to `/var/lib/motioneye/CameraX/...` in container
- Backend expects files at `motioneye_media/CameraX/...` on host
- Verify volume mount is working correctly
- Check if files exist in `motioneye_media` directory

### Verification Steps:

1. **Trigger manual snapshot in MotionEye**:
   - Open http://localhost:8765
   - Go to camera settings
   - Click "Take Snapshot"
   - Check if webhook is received

2. **Check webhook log immediately after motion**:
   ```bash
   docker exec wildlife-motioneye tail -f /tmp/webhook_debug.log
   ```
   Then walk past camera and watch for new entries

3. **Test webhook manually**:
   ```bash
   docker exec wildlife-motioneye curl -X POST http://host.docker.internal:8001/api/motioneye/webhook \
     -H "Content-Type: application/json" \
     -d '{"camera_id": 3, "file_path": "/var/lib/motioneye/Camera3/2025-12-10/test.jpg", "type": "picture_save", "timestamp": "2025-12-10T15:00:00Z"}'
   ```

### Updated Webhook Script:
The webhook script now logs HTTP response codes and errors. Check `/tmp/webhook_debug.log` for:
- ✅ "Webhook sent successfully - HTTP 200"
- ❌ "Webhook FAILED - HTTP XXX"

### Next Steps:
1. Monitor webhook debug log for next motion event
2. Check backend logs simultaneously
3. Verify files are being created in motioneye_media
4. Check if detections appear in database (even if filtered)

