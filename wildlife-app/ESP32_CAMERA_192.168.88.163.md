# ESP32 Camera Setup - 192.168.88.163

## Camera Information
- **IP Address:** 192.168.88.163
- **Suggested URL:** `http://192.168.88.163/stream`
- **Alternative URLs to try:**
  - `http://192.168.88.163/jpg`
  - `http://192.168.88.163/mjpeg`
  - `http://192.168.88.163/video`

---

## Method 1: Add via Web Interface (Recommended)

1. **Open the Wildlife App:**
   - Navigate to: http://localhost:3000/cameras

2. **Click "Add Camera"**

3. **Fill in the form:**
   - **Camera Name:** ESP32 Camera (or your preferred name)
   - **RTSP URL:** `http://192.168.88.163/stream`
   - **Width:** 640
   - **Height:** 480
   - **Framerate:** 10
   - **Stream Quality:** 75
   - **Detection Enabled:** ✓ (if you want motion detection)

4. **Click "Add Camera"**

---

## Method 2: Add via MotionEye Directly

1. **Open MotionEye:**
   - Navigate to: http://localhost:8765

2. **Add Camera:**
   - Click "Add Camera"
   - Select "Network Camera"
   - Enter URL: `http://192.168.88.163/stream`
   - Configure settings as needed
   - Save

3. **Sync with Wildlife App:**
   - Go to: http://localhost:3000/cameras
   - Click "Sync Cameras from MotionEye"

---

## Method 3: Find the Correct Stream URL

If `/stream` doesn't work:

1. **Open ESP32 Web Interface:**
   - Navigate to: http://192.168.88.163/
   - Look for links or buttons that say "Stream", "Video", "Live", etc.

2. **Test URLs in Browser:**
   - Try each URL in your browser:
     - `http://192.168.88.163/stream`
     - `http://192.168.88.163/jpg`
     - `http://192.168.88.163/mjpeg`
     - `http://192.168.88.163/video`
   - The one that shows video is the correct URL

3. **Use the working URL** when adding the camera

---

## Troubleshooting

### ESP32 Not Reachable

If you can't access the ESP32:

1. **Check ESP32 Status:**
   - Verify ESP32 is powered on
   - Check WiFi connection
   - Verify IP address in MikroTik router

2. **Test Connectivity:**
   ```powershell
   ping 192.168.88.163
   ```

3. **Check Firewall:**
   - Ensure firewall isn't blocking connections
   - Verify ESP32 and server are on same network

### MotionEye Not Running

If camera addition fails:

1. **Start MotionEye:**
   ```bash
   docker-compose up motioneye -d
   ```
   Or use: `scripts\control.bat`

2. **Verify MotionEye:**
   - Check: http://localhost:8765
   - Should show MotionEye interface

### Stream URL Not Working

If the stream doesn't load:

1. **Test URL Directly:**
   - Open the URL in a browser
   - You should see video or an image

2. **Check ESP32 Firmware:**
   - Some ESP32 firmwares use different paths
   - Check ESP32 serial monitor for available endpoints

3. **Update Camera URL:**
   - Go to: http://localhost:3000/cameras
   - Click on the camera
   - Edit the URL
   - Save

---

## Recommended Settings for ESP32

- **Resolution:** 640x480 (or your ESP32's resolution)
- **Framerate:** 10 FPS (ESP32 typically can't do 30fps)
- **Stream Quality:** 75
- **Stream Max Rate:** 10 (match framerate)
- **Detection Threshold:** 2500 (may need adjustment)
- **Detection Smart Mask Speed:** 5

---

## Next Steps

After adding the camera:

1. ✅ Verify it appears in the camera list
2. ✅ Test the live stream
3. ✅ Adjust detection settings if needed
4. ✅ Monitor for detections

---

## Need Help?

If you encounter issues:

1. Check backend logs for errors
2. Verify ESP32 is accessible from your server
3. Test the stream URL directly in a browser
4. Review MotionEye logs: `docker-compose logs motioneye`

