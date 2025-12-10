# Webhook Detection Fix Summary

## Issues Found and Fixed

### Issue 1: Path Mapping Error ✅ FIXED
**Problem:** Backend was looking for files in `wildlife-app/backend/motioneye_media` instead of `wildlife-app/motioneye_media`

**Fix:** Updated path calculation in `routers/webhooks.py` to correctly go up 3 levels:
- From: `wildlife-app/backend/routers/webhooks.py`
- To: `wildlife-app/`

**Status:** Code fixed, but **BACKEND MUST BE RESTARTED** for changes to take effect.

### Issue 2: MotionEye Webhook Script ✅ CREATED
**Problem:** MotionEye's `meyectl.py webhook` command was not executing

**Fix:** Created custom webhook script `/etc/motioneye/send_webhook.sh` that:
- Extracts camera ID from file path
- Sends JSON payload to backend
- Logs execution for debugging

**Status:** Script created and all camera configs updated.

### Issue 3: Camera Config Updates ✅ COMPLETED
**Problem:** Camera configs were using non-working `meyectl.py webhook` command

**Fix:** Updated all 7 camera configs to use the new `send_webhook.sh` script:
```
on_picture_save ... /etc/motioneye/send_webhook.sh %$ %f picture_save %t
```

**Status:** All configs updated, MotionEye restarted.

## Next Steps

1. **RESTART THE BACKEND** - This is critical for the path fix to work!
   ```bash
   # Stop and restart the backend server
   # Or use: scripts/control.bat -> Restart All Services
   ```

2. **Wait for Motion Events** - MotionEye needs to detect motion and save pictures

3. **Monitor Webhooks:**
   ```bash
   cd wildlife-app/backend
   python check_recent_webhooks.py
   ```

4. **Check Debug Log:**
   ```bash
   docker exec wildlife-motioneye tail -f /tmp/webhook_debug.log
   ```

## Testing

To test if webhooks work after backend restart:
```bash
# Find a real file
docker exec wildlife-motioneye find /var/lib/motioneye -name "*.jpg" -mmin -60 | head -1

# Test webhook manually
# Use the file path from above
curl -X POST http://localhost:8001/api/motioneye/webhook \
  -H "Content-Type: application/json" \
  -d '{"camera_id": 1, "file_path": "/var/lib/motioneye/Camera1/...", "type": "picture_save"}'
```

## Expected Behavior

After backend restart:
1. MotionEye detects motion and saves picture
2. `send_webhook.sh` script executes
3. Webhook sent to backend
4. Backend finds file in correct location (`wildlife-app/motioneye_media/...`)
5. Detection created in database
6. Detection appears in frontend

