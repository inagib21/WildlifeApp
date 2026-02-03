# Fix Webhooks - Get Detections Working

## The Problem
No detections because MotionEye isn't sending webhook events to the backend.

## The Solution (5 minutes)

### Step 1: Open MotionEye
1. Open your browser
2. Go to: **http://localhost:8765**
3. Login if prompted: `admin` / `admin`

### Step 2: Configure Webhook for ONE Camera (Test First)
1. **Click on any camera** (start with Camera 1 to test)
2. **Click the "Motion Detection" tab** (or look for "Advanced" settings)
3. **Scroll down** to find the **"on_picture_save"** field
4. **Copy this exact command:**
   ```
   curl -X POST http://localhost:8001/api/motioneye/webhook -F file_path=%f -F camera_id=%c
   ```
5. **Paste it into the "on_picture_save" field**
6. **Make sure these are checked:**
   - ✅ **Motion Detection**: ON
   - ✅ **Picture Output Motion**: ON
7. **Click "Save"** or "Apply" button

### Step 3: Test It
1. **Wave at the camera** or trigger motion detection
2. **Wait 10-30 seconds**
3. **Go to Detections page** in Wildlife app
4. **You should see a new detection!** ✅

### Step 4: Configure All Other Cameras
Once you confirm it works, repeat Step 2 for all remaining cameras.

## Quick Copy-Paste Command

```
curl -X POST http://localhost:8001/api/motioneye/webhook -F file_path=%f -F camera_id=%c
```

## Troubleshooting

### Still no detections after configuring?

1. **Check backend is running:**
   - Open: http://localhost:8001/health
   - Should show: `{"status": "healthy"}`

2. **Check MotionEye can reach backend:**
   - MotionEye runs in Docker
   - If backend is on `localhost:8001`, MotionEye should reach it
   - If not working, try: `http://host.docker.internal:8001/api/motioneye/webhook`

3. **Check MotionEye logs:**
   - Look for webhook execution errors
   - Verify curl command is working

4. **Test webhook manually:**
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8001/api/motioneye/webhook" -Method POST -Body @{file_path="/test"; camera_id="1"}
   ```

### Alternative Command (if curl doesn't work)

If curl isn't available in MotionEye container, try wget:
```
wget --post-data "file_path=%f&camera_id=%c" -O - http://localhost:8001/api/motioneye/webhook
```

## Visual Guide

1. **MotionEye Interface:**
   ```
   Camera Settings
   ├── General
   ├── Video Device
   ├── Motion Detection  ← Click here
   │   ├── Motion Detection: [ON]
   │   ├── Picture Output Motion: [ON]
   │   └── on_picture_save: [paste webhook command here]
   └── ...
   ```

2. **The webhook command goes in "on_picture_save" field**

## After Configuration

1. **Restart backend** (to apply the `_is_video_file` fix)
2. **Trigger motion** on a camera
3. **Check Detections page** - should see new detections!

## Need Help?

If webhooks still don't work:
1. Check backend logs for webhook processing
2. Verify MotionEye can execute curl commands
3. Test webhook endpoint manually (see troubleshooting above)
