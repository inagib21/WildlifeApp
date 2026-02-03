# MotionEye Webhook Configuration Guide

## Quick Setup (5 minutes)

### Step 1: Open MotionEye
1. Go to: **http://localhost:8765**
2. Log in if required

### Step 2: Configure Webhooks for Each Camera

For **each camera** (you can do them one at a time or all at once):

1. **Click on the camera** you want to configure
2. **Go to "Motion Detection" or "Advanced" settings**
3. **Find the `on_picture_save` field**
4. **Paste this command:**
   ```
   curl -X POST http://localhost:8001/api/motioneye/webhook -F file_path=%f -F camera_id=%c
   ```
5. **Verify these settings are enabled:**
   - ✅ Motion Detection: **ON**
   - ✅ Picture Output Motion: **ON**
6. **Click "Save" or "Apply"**

### Step 3: Test It

1. **Trigger motion detection** on a camera (wave at it, move something)
2. **Check backend logs** - you should see webhook processing messages
3. **Check Detections page** - new detections should appear within seconds

## Webhook Command Options

### Option 1: Basic (Recommended)
```
curl -X POST http://localhost:8001/api/motioneye/webhook -F file_path=%f -F camera_id=%c
```

### Option 2: With Timestamp
```
curl -X POST http://localhost:8001/api/motioneye/webhook -F file_path=%f -F camera_id=%c -F timestamp=%t
```

### Option 3: Using wget (if curl not available)
```
wget --post-data "file_path=%f&camera_id=%c" -O - http://localhost:8001/api/motioneye/webhook
```

## MotionEye Variables

- `%f` = Full file path
- `%c` = Camera ID
- `%t` = Timestamp
- `%n` = Camera name

## Troubleshooting

### No detections appearing?

1. **Check backend is running:**
   ```bash
   curl http://localhost:8001/health
   ```

2. **Test webhook endpoint:**
   ```bash
   curl -X POST http://localhost:8001/api/motioneye/webhook -F file_path=/test -F camera_id=1
   ```

3. **Check MotionEye logs:**
   - Look for webhook execution errors
   - Verify curl/wget is available in MotionEye's environment

4. **Verify webhook command:**
   - Make sure the webhook URL is correct: `http://localhost:8001/api/motioneye/webhook`
   - Check that MotionEye can reach localhost:8001

5. **Check backend logs:**
   - Look for webhook processing messages
   - Check for errors or filtered detections

### Webhook not executing?

- **MotionEye may need curl/wget installed**
- **Check MotionEye's system requirements**
- **Try the wget alternative command**

### Detections filtered out?

- **Check confidence thresholds** - detections need >= 0.10 confidence
- **Check backend logs** for "Detection filtered" messages
- **Verify AI processing is enabled** in backend settings

## Verification

After configuring, run:
```bash
cd wildlife-app\backend
python scripts\auto_configure_webhooks.py --verify-only
```

This will check which cameras have webhooks configured.

## Quick Reference

**Webhook URL:** `http://localhost:8001/api/motioneye/webhook`

**Command to add:**
```
curl -X POST http://localhost:8001/api/motioneye/webhook -F file_path=%f -F camera_id=%c
```

**Where to add it:** MotionEye → Camera → Motion Detection → `on_picture_save`

**Required settings:**
- Motion Detection: **ON**
- Picture Output Motion: **ON**
