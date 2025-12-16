# Camera Troubleshooting Guide

## Issue: Camera Not Showing Image in MotionEye

### Quick Fixes

1. **Check Camera Credentials**
   - Thingino cameras typically use: `thingino:thingino`
   - Verify in MotionEye config: `netcam_userpass thingino:thingino`

2. **Verify RTSP URL Format**
   - Correct format: `rtsp://192.168.88.XXX:554/ch0`
   - For Thingino: `rtsp://thingino:thingino@192.168.88.XXX:554/ch0`

3. **Test Camera Connection**
   ```bash
   cd wildlife-app/backend
   python test_rtsp_camera.py rtsp://thingino:thingino@192.168.88.68:554/ch0 9
   ```

4. **Restart MotionEye**
   ```bash
   docker restart wildlife-motioneye
   ```
   Or if using docker-compose:
   ```bash
   docker-compose restart motioneye
   ```

### Common Issues

#### 1. Wrong Credentials
**Symptoms:** Camera shows "No image" or black screen
**Solution:** 
- Check camera config file: `wildlife-app/motioneye_config/camera-X.conf`
- Verify `netcam_userpass` matches other working cameras
- For Thingino: Should be `thingino:thingino`

#### 2. Camera Not Reachable
**Symptoms:** Connection timeout, no response
**Solution:**
- Ping the camera IP: `ping 192.168.88.68`
- Check if camera is powered on
- Verify camera is connected to WiFi
- Check router DHCP leases for correct IP

#### 3. Wrong RTSP Path
**Symptoms:** Connection refused or 404 error
**Solution:**
- Thingino cameras usually use: `/ch0`
- Try alternative paths: `/stream`, `/h264`, `/main`
- Test with VLC player first

#### 4. MotionEye Not Loading Config
**Symptoms:** Changes don't take effect
**Solution:**
- Restart MotionEye container
- Check MotionEye logs: `docker logs wildlife-motioneye`
- Verify config file is in correct location

### Testing Steps

1. **Test Camera IP**
   ```powershell
   ping 192.168.88.68
   ```

2. **Test RTSP Stream (if you have VLC)**
   - Open VLC Media Player
   - Media → Open Network Stream
   - Enter: `rtsp://thingino:thingino@192.168.88.68:554/ch0`
   - Click Play

3. **Test with Diagnostic Script**
   ```bash
   cd wildlife-app/backend
   python test_rtsp_camera.py rtsp://thingino:thingino@192.168.88.68:554/ch0 9
   ```

4. **Check MotionEye Logs**
   ```bash
   docker logs wildlife-motioneye --tail 50
   ```

### Camera Configuration Checklist

When adding a new Thingino camera, verify:

- [ ] IP address is correct and camera is reachable
- [ ] RTSP URL format: `rtsp://192.168.88.XXX:554/ch0`
- [ ] Credentials: `netcam_userpass thingino:thingino`
- [ ] Framerate: `framerate 10` (not too low)
- [ ] Stream port is unique (9081, 9082, 9083, etc.)
- [ ] Motion detection is enabled: `motion_detection on`
- [ ] Picture output is enabled: `picture_output on`
- [ ] Webhook is configured: `on_picture_save` includes `send_webhook.sh`

### Example Working Configuration

```conf
netcam_url rtsp://192.168.88.68:554/ch0
netcam_userpass thingino:thingino
width 640
height 480
camera_name Camera9
framerate 10
stream_port 9089
stream_maxrate 15
motion_detection on
picture_output on
threshold 19208
minimum_motion_frames 2
event_gap 1
```

### Still Not Working?

1. **Check MotionEye Web Interface**
   - Go to: http://localhost:8765
   - Click on the camera
   - Check for error messages

2. **Verify Camera in Database**
   ```bash
   cd wildlife-app/backend
   python check_db.py
   ```

3. **Check Webhook Configuration**
   - Verify `send_webhook.sh` is executable
   - Check webhook logs in backend

4. **Compare with Working Camera**
   - Look at a working camera config (e.g., `camera-1.conf`)
   - Copy settings that differ

### Need More Help?

- Check MotionEye documentation: https://github.com/motioneye-project/motioneye
- Review camera logs in MotionEye web interface
- Check backend logs for webhook errors

