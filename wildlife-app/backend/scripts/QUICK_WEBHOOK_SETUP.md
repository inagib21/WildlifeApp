# Quick Webhook Setup - Get Detections Working NOW

## The Problem
No detections since January 14th because MotionEye webhooks are not configured.

## The Solution (5 minutes)

### Step 1: Open MotionEye
Go to: **http://localhost:8765**
- Login: `admin` / `admin` (if prompted)

### Step 2: Configure ONE Camera First (Test)
1. Click on **any camera** (start with Camera 1)
2. Click **"Motion Detection"** tab (or "Advanced" settings)
3. Scroll down to find **"on_picture_save"** field
4. **Paste this exact command:**
   ```
   curl -X POST http://localhost:8001/api/motioneye/webhook -F file_path=%f -F camera_id=%c
   ```
5. Make sure these are checked:
   - ✅ **Motion Detection**: ON
   - ✅ **Picture Output Motion**: ON
6. Click **"Save"** or **"Apply"**

### Step 3: Test It
1. **Wave at the camera** or trigger motion
2. **Wait 10-30 seconds**
3. **Check Detections page** - you should see a new detection!

### Step 4: Configure Remaining Cameras
Once you confirm it works on one camera, repeat Step 2 for all other cameras.

## Troubleshooting

### Still no detections?
1. **Check backend is running:**
   - Open: http://localhost:8001/health
   - Should show: `{"status": "healthy"}`

2. **Check MotionEye can reach backend:**
   - MotionEye runs in Docker, backend runs on host
   - If backend is on `localhost:8001`, MotionEye should be able to reach it
   - If not, try: `http://host.docker.internal:8001/api/motioneye/webhook`

3. **Check MotionEye logs:**
   - Look for webhook execution errors
   - Verify curl is available in MotionEye container

4. **Test webhook manually:**
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8001/api/motioneye/webhook" -Method POST -Body @{file_path="/test"; camera_id="1"}
   ```

## Alternative Webhook Command (if curl doesn't work)

If curl isn't available in MotionEye, try wget:
```
wget --post-data "file_path=%f&camera_id=%c" -O - http://localhost:8001/api/motioneye/webhook
```

## Quick Copy-Paste Command

```
curl -X POST http://localhost:8001/api/motioneye/webhook -F file_path=%f -F camera_id=%c
```

Copy the command above and paste it into each camera's `on_picture_save` field in MotionEye.
