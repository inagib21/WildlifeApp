# ESP32 Webcam Setup Guide

This guide will help you connect an ESP32 webcam to your Wildlife Monitoring System.

## Prerequisites

1. ESP32 webcam is powered on and connected to your network
2. ESP32 has an IP address assigned (you mentioned it's already in MikroTik)
3. Backend server is running (http://localhost:8001)
4. MotionEye is running (http://localhost:8765)

---

## Step 1: Find Your ESP32's IP Address

Since you mentioned the ESP32 already has an IP in MikroTik:

1. **Check MikroTik Router:**
   - Log into your MikroTik router
   - Go to **IP > DHCP Server > Leases**
   - Look for your ESP32 device (may show as "ESP32" or the device name you configured)
   - Note the IP address (e.g., `192.168.88.XXX`)

2. **Alternative - Check from ESP32:**
   - If your ESP32 has a serial monitor or web interface, it may display the IP
   - Common ESP32 webcam libraries show IP on startup

---

## Step 2: Determine ESP32 Stream URL Format

ESP32 webcams typically use HTTP/MJPEG streams. Common URL formats:

### Common ESP32 Webcam URLs:

1. **ESP32-CAM (Arduino/ESP-IDF):**
   - MJPEG Stream: `http://IP_ADDRESS/stream`
   - JPEG Snapshot: `http://IP_ADDRESS/capture`
   - Example: `http://192.168.88.100/stream`

2. **ESP32 with CameraWebServer:**
   - MJPEG Stream: `http://IP_ADDRESS:81/stream`
   - JPEG Snapshot: `http://IP_ADDRESS:81/capture`
   - Example: `http://192.168.88.100:81/stream`

3. **Custom ESP32 Firmware:**
   - Check your firmware documentation
   - Common paths: `/jpg`, `/mjpeg`, `/video`, `/stream`

### Test the Stream URL:

**Option A: Browser Test**
1. Open a web browser
2. Navigate to: `http://YOUR_ESP32_IP/stream` (or your specific path)
3. You should see a live video stream

**Option B: VLC Test**
1. Open VLC Media Player
2. Go to **Media > Open Network Stream**
3. Enter: `http://YOUR_ESP32_IP/stream`
4. Click Play

**Option C: Command Line (PowerShell)**
```powershell
# Test if ESP32 responds
Invoke-WebRequest -Uri "http://YOUR_ESP32_IP/stream" -Method Head -TimeoutSec 5
```

---

## Step 3: Add ESP32 Camera to System

### Method 1: Using the Web Interface (Recommended)

1. **Open the Wildlife App:**
   - Navigate to: http://localhost:3000 (or your frontend URL)
   - Go to **Cameras** page

2. **Add New Camera:**
   - Click **"Add Camera"** button
   - Fill in the form:
     - **Camera Name:** e.g., "ESP32 Backyard Camera"
     - **RTSP URL:** Enter your ESP32 stream URL (e.g., `http://192.168.88.100/stream`)
     - **Width:** 640 (or your ESP32 resolution)
     - **Height:** 480 (or your ESP32 resolution)
     - **Framerate:** 10-15 (ESP32 typically can't do 30fps)
     - **Stream Quality:** 75-85
     - **Detection Enabled:** ✓ (if you want motion detection)
   - Click **"Add Camera"**

### Method 2: Using the API Directly

**Using PowerShell:**
```powershell
$cameraData = @{
    name = "ESP32 Backyard Camera"
    url = "http://192.168.88.100/stream"
    width = 640
    height = 480
    framerate = 10
    stream_quality = 75
    stream_maxrate = 10
    detection_enabled = $true
    detection_threshold = 1500
    movie_output = $true
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8001/api/cameras" `
    -Method Post `
    -ContentType "application/json" `
    -Body $cameraData
```

**Using curl (if available):**
```bash
curl -X POST http://localhost:8001/api/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ESP32 Backyard Camera",
    "url": "http://192.168.88.100/stream",
    "width": 640,
    "height": 480,
    "framerate": 10,
    "stream_quality": 75,
    "stream_maxrate": 10,
    "detection_enabled": true,
    "detection_threshold": 1500
  }'
```

### Method 3: Using Swagger UI

1. Open: http://localhost:8001/docs
2. Find the **POST /api/cameras** endpoint
3. Click **"Try it out"**
4. Enter your camera data in JSON format:
```json
{
  "name": "ESP32 Backyard Camera",
  "url": "http://192.168.88.100/stream",
  "width": 640,
  "height": 480,
  "framerate": 10,
  "stream_quality": 75,
  "stream_maxrate": 10,
  "detection_enabled": true,
  "detection_threshold": 1500,
  "movie_output": true
}
```
5. Click **"Execute"**

---

## Step 4: Recommended ESP32 Camera Settings

### For MotionEye Integration:

Since ESP32 webcams are typically lower resolution and framerate:

```json
{
  "name": "ESP32 Camera",
  "url": "http://YOUR_ESP32_IP/stream",
  "width": 640,
  "height": 480,
  "framerate": 10,
  "stream_port": 8081,
  "stream_quality": 75,
  "stream_maxrate": 10,
  "stream_localhost": false,
  "detection_enabled": true,
  "detection_threshold": 2000,
  "detection_smart_mask_speed": 5,
  "movie_output": true,
  "movie_quality": 75,
  "movie_codec": "mkv",
  "snapshot_interval": 0,
  "target_dir": "./motioneye_media"
}
```

### Settings Explanation:

- **framerate: 10** - ESP32 typically can't handle 30fps
- **stream_maxrate: 10** - Match framerate
- **detection_threshold: 2000** - May need adjustment based on ESP32 image quality
- **stream_quality: 75** - Good balance for ESP32 bandwidth

---

## Step 5: Verify Camera is Working

1. **Check Camera List:**
   - Go to http://localhost:3000/cameras
   - Your ESP32 camera should appear in the list

2. **View Live Stream:**
   - Click on your ESP32 camera
   - The stream should load (may take a few seconds)

3. **Check MotionEye:**
   - Go to http://localhost:8765
   - Your ESP32 camera should appear in the camera list
   - Click on it to view the stream

4. **Test Motion Detection:**
   - If detection is enabled, trigger motion in front of the camera
   - Check the Detections page for new detections

---

## Troubleshooting

### Camera Not Appearing

1. **Check ESP32 is Accessible:**
   ```powershell
   # Ping test
   ping YOUR_ESP32_IP
   
   # HTTP test
   Invoke-WebRequest -Uri "http://YOUR_ESP32_IP/stream" -TimeoutSec 5
   ```

2. **Check URL Format:**
   - Ensure URL starts with `http://` (not `https://` unless ESP32 has SSL)
   - Verify the path is correct (`/stream`, `/mjpeg`, etc.)
   - Check if port is needed (e.g., `:81`)

3. **Check Backend Logs:**
   - Look for errors in the backend console
   - Check for "Camera added" or error messages

### Stream Not Loading

1. **ESP32 Firmware Issues:**
   - ESP32 may need to be reset
   - Check ESP32 serial monitor for errors
   - Verify ESP32 has stable WiFi connection

2. **Network Issues:**
   - Ensure ESP32 and server are on same network
   - Check firewall isn't blocking connections
   - Verify IP address hasn't changed (check DHCP lease)

3. **MotionEye Issues:**
   - MotionEye may need time to connect to ESP32
   - Check MotionEye logs: `docker-compose logs motioneye`
   - Try restarting MotionEye: `docker-compose restart motioneye`

### Poor Image Quality

1. **Adjust Stream Quality:**
   - Increase `stream_quality` to 85-100 (may cause lag)
   - Decrease `framerate` to 5-8 if needed

2. **ESP32 Settings:**
   - Check ESP32 firmware for quality settings
   - Some ESP32 firmwares allow adjusting JPEG quality
   - Consider upgrading ESP32 firmware if possible

### Motion Detection Not Working

1. **Adjust Detection Threshold:**
   - ESP32 images may be noisier
   - Try increasing `detection_threshold` to 3000-5000
   - Adjust `detection_smart_mask_speed` to 5-10

2. **Check Detection Settings:**
   - Verify `detection_enabled` is `true`
   - Check MotionEye detection settings for the camera

---

## ESP32 Webcam Firmware Recommendations

If you're building your own ESP32 webcam firmware, ensure it provides:

1. **MJPEG Stream Endpoint:**
   - Path: `/stream` or `/mjpeg`
   - Format: MJPEG (Motion JPEG)
   - Resolution: 640x480 or higher

2. **Stable Connection:**
   - Use WiFi with good signal strength
   - Implement connection retry logic
   - Consider using static IP or DHCP reservation

3. **Performance:**
   - Optimize for 10-15 FPS
   - Use appropriate JPEG quality (70-85)
   - Consider frame skipping if needed

---

## Example: Complete ESP32 Camera Configuration

Here's a complete example for a typical ESP32-CAM:

```json
{
  "name": "ESP32 Backyard Camera",
  "url": "http://192.168.88.100/stream",
  "width": 640,
  "height": 480,
  "framerate": 10,
  "stream_port": 8081,
  "stream_quality": 75,
  "stream_maxrate": 10,
  "stream_localhost": false,
  "detection_enabled": true,
  "detection_threshold": 2500,
  "detection_smart_mask_speed": 5,
  "movie_output": true,
  "movie_quality": 75,
  "movie_codec": "mkv",
  "snapshot_interval": 0,
  "target_dir": "./motioneye_media"
}
```

---

## Next Steps

After adding your ESP32 camera:

1. ✅ Verify it appears in the camera list
2. ✅ Test the live stream
3. ✅ Adjust detection settings if needed
4. ✅ Monitor for detections
5. ✅ Check that images are being processed by SpeciesNet

---

## Need Help?

If you encounter issues:

1. Check the backend logs for errors
2. Verify ESP32 is accessible from your server
3. Test the stream URL directly in a browser
4. Review MotionEye logs for connection issues
5. Check the Troubleshooting section above

---

**Note:** ESP32 webcams typically have lower performance than dedicated IP cameras. Expect:
- Lower framerates (5-15 FPS)
- Possible connection drops
- Lower image quality
- Higher latency

These limitations are normal for ESP32-based solutions.

