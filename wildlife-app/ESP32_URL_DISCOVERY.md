# How to Find Your ESP32 Webcam Stream URL

This guide will help you discover the correct stream URL for your ESP32 webcam.

---

## Quick Method: Use the Discovery Script

**PowerShell Script (Easiest):**
```powershell
cd C:\Users\Edwin\Documents\Wildlife\scripts
.\find-esp32-stream-url.ps1 -Esp32Ip "192.168.88.XXX"
```

The script will automatically test common ESP32 stream paths and tell you which one works!

---

## Manual Method: Step-by-Step

### Step 1: Get Your ESP32 IP Address

Since you mentioned it's already in MikroTik:

1. **Log into MikroTik Router:**
   - Open your browser and go to your MikroTik router's IP (usually `192.168.88.1`)
   - Log in with your credentials

2. **Check DHCP Leases:**
   - Go to **IP > DHCP Server > Leases**
   - Look for your ESP32 device
   - Note the IP address (e.g., `192.168.88.100`)

3. **Alternative - Check ESP32 Serial Monitor:**
   - If your ESP32 is connected via USB, open the serial monitor
   - The IP address is usually printed on startup

### Step 2: Test Common Stream URLs

ESP32 webcams typically use one of these URLs. Test each in your browser:

#### Common ESP32 Stream URLs:

1. **ESP32-CAM (Arduino):**
   ```
   http://YOUR_ESP32_IP/stream
   ```
   Example: `http://192.168.88.100/stream`

2. **CameraWebServer (Arduino):**
   ```
   http://YOUR_ESP32_IP:81/stream
   ```
   Example: `http://192.168.88.100:81/stream`

3. **Other Common Paths:**
   - `http://YOUR_ESP32_IP/mjpeg`
   - `http://YOUR_ESP32_IP/video`
   - `http://YOUR_ESP32_IP/jpg`
   - `http://YOUR_ESP32_IP/capture`
   - `http://YOUR_ESP32_IP/stream.mjpg`

### Step 3: Test in Browser

1. **Open your web browser** (Chrome, Firefox, Edge, etc.)

2. **Navigate to the URL:**
   - Start with: `http://YOUR_ESP32_IP/stream`
   - If that doesn't work, try: `http://YOUR_ESP32_IP:81/stream`
   - Continue trying other paths from the list above

3. **What to Look For:**
   - ✅ **Success:** You see a live video stream (MJPEG video)
   - ❌ **Not Found:** Browser shows "404 Not Found" or "Page not found"
   - ❌ **Connection Error:** Browser can't connect (check IP address)

### Step 4: Verify It's a Stream

When you find the right URL, you should see:
- A continuous video stream (not a single image)
- The video updates in real-time
- The page keeps loading (streaming continuously)

**Note:** Some browsers may show a single JPEG image instead of a stream. If you see an image that updates, that's also a valid stream URL.

---

## Method 3: Check ESP32 Web Interface

Many ESP32 webcam firmwares include a web interface:

1. **Open ESP32 Root URL:**
   ```
   http://YOUR_ESP32_IP
   ```
   Example: `http://192.168.88.100`

2. **Look for Links:**
   - Click on links that say "Stream", "Video", "Live", "Camera", etc.
   - The link will show you the correct path

3. **Check Page Source:**
   - Right-click on the page → "View Page Source"
   - Look for URLs containing "stream", "mjpeg", "video", etc.

---

## Method 4: Check ESP32 Serial Monitor

If your ESP32 is connected via USB:

1. **Open Serial Monitor** (Arduino IDE, PlatformIO, etc.)
2. **Look for startup messages** that might show:
   - Stream URL
   - Available endpoints
   - Web server information

Example output:
```
WiFi connected!
IP address: 192.168.88.100
Camera Ready! Use 'http://192.168.88.100/stream' to connect
```

---

## Method 5: Check Your ESP32 Firmware Code

If you have access to the ESP32 code:

1. **Look for web server routes:**
   ```cpp
   // Arduino/ESP-IDF example
   server.on("/stream", handleStream);
   server.on("/mjpeg", handleMJPEG);
   ```

2. **Check the route handler** to see what path it uses

3. **Common firmware examples:**
   - **ESP32-CAM (Arduino):** Usually `/stream`
   - **CameraWebServer:** Usually `:81/stream`
   - **Custom firmware:** Check your code

---

## Testing with PowerShell

You can also test URLs from PowerShell:

```powershell
# Test if ESP32 responds
$ip = "192.168.88.100"
Invoke-WebRequest -Uri "http://$ip/stream" -Method Head -TimeoutSec 5

# Test different paths
$paths = @("/stream", "/mjpeg", "/video", "/jpg")
foreach ($path in $paths) {
    try {
        $response = Invoke-WebRequest -Uri "http://$ip$path" -Method Head -TimeoutSec 3
        Write-Host "✓ Found: http://$ip$path" -ForegroundColor Green
    } catch {
        Write-Host "✗ Not found: http://$ip$path" -ForegroundColor Red
    }
}
```

---

## Testing with VLC Media Player

VLC can help test stream URLs:

1. **Open VLC Media Player**
2. **Go to:** Media → Open Network Stream
3. **Enter URL:** `http://YOUR_ESP32_IP/stream`
4. **Click Play**
5. If video appears, the URL is correct!

---

## Common Issues

### "Connection Refused" or "Cannot Connect"

**Possible Causes:**
- ESP32 is not powered on
- ESP32 is not connected to WiFi
- IP address has changed (check DHCP leases again)
- ESP32 is on a different network

**Solutions:**
- Verify ESP32 is powered and connected
- Check MikroTik DHCP leases for current IP
- Try pinging the ESP32: `ping 192.168.88.XXX`

### "404 Not Found"

**Possible Causes:**
- Wrong stream path
- ESP32 firmware uses different path

**Solutions:**
- Try other common paths (`/mjpeg`, `/video`, etc.)
- Check ESP32 web interface for correct path
- Review ESP32 firmware code

### "Single Image Instead of Stream"

**This is OK!** Some ESP32 firmwares serve single JPEG images that update. This still works with MotionEye. Use the URL that shows the image.

---

## Once You Find the URL

After you discover the correct stream URL:

1. **Test it works:**
   - Open in browser and verify you see video/image
   - Note the exact URL (including port if any)

2. **Add to Wildlife System:**
   ```powershell
   .\scripts\add-esp32-camera.ps1 -CameraName "ESP32 Camera" -Esp32Ip "192.168.88.XXX" -StreamPath "/stream"
   ```

   Or use the web interface:
   - Go to http://localhost:3000/cameras
   - Click "Add Camera"
   - Enter the full URL: `http://192.168.88.XXX/stream`

---

## Example: Complete Discovery Process

1. **Get IP from MikroTik:** `192.168.88.100`
2. **Test in browser:** `http://192.168.88.100/stream` → ✅ Works!
3. **Verify it's a stream:** Video appears and updates
4. **Add to system:** Use `http://192.168.88.100/stream` as the camera URL

---

## Still Can't Find It?

If none of the common paths work:

1. **Check ESP32 Serial Output:**
   - Connect ESP32 via USB
   - Open serial monitor
   - Look for startup messages with URLs

2. **Access ESP32 Web Interface:**
   - Go to `http://YOUR_ESP32_IP`
   - Look for links or documentation

3. **Review Firmware:**
   - Check the ESP32 code for web server routes
   - Look for `server.on()` or similar route definitions

4. **Try Port Scanning:**
   - ESP32 might use a non-standard port (81, 8080, etc.)
   - Test: `http://YOUR_ESP32_IP:81/stream`

---

**Need Help?** Share your ESP32 model or firmware name, and I can help identify the correct stream path!

