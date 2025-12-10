# Detection Optimization Guide

## Summary of Issues Found

### Cameras with Problems:
1. **Camera 2 (wyzecam3-03)**: No detections ever recorded
2. **Camera 5 (wyzecam3-04)**: No detections ever recorded  
3. **Camera 6 (WYZECAM3-02)**: Last detection 166.5 hours ago (almost a week!)

### Current Detection Statistics:
- **Total Detections (Last 24h)**: 97
- **Total Detections (Last 7 days)**: 436
- **Average per Camera (24h)**: 12.1
- **Average per Camera (7 days)**: 54.5

### Issues Identified:
1. **Motion thresholds too high** (45000-46000) - missing smaller wildlife movements
2. **Minimum motion frames too high** (4 frames) - slow to trigger
3. **Event gap too long** (3 seconds) - missing rapid movements
4. **Many "Unknown" and "Blank" detections** - suggests thresholds need adjustment

## Optimizations Applied

### 1. Motion Detection Thresholds
- **Before**: 45000-46000 (very high, only detects large motion)
- **After**: 29000-30000 (35% reduction, more sensitive)
- **Impact**: Will detect smaller wildlife movements, birds, small animals

### 2. Minimum Motion Frames
- **Before**: 4 frames (requires sustained motion)
- **After**: 2 frames (faster triggering)
- **Impact**: Faster detection of quick movements

### 3. Event Gap
- **Before**: 3 seconds (long gap between events)
- **After**: 1 second (shorter gap)
- **Impact**: More frequent detections, won't miss rapid movements

### 4. Confidence Threshold
- **Before**: 0.15 (15% minimum confidence)
- **After**: 0.10 (10% minimum confidence)
- **Impact**: Saves more detections, even with lower confidence

## Next Steps

### 1. Restart MotionEye
The optimized settings are in the config files. You need to restart MotionEye to apply them:

```bash
docker restart wildlife-motioneye
```

Or if using docker-compose:
```bash
docker-compose restart motioneye
```

### 2. Monitor Detection Rates
After restarting, monitor the detection rates:

```bash
cd wildlife-app/backend
python analyze_camera_detections.py
```

You should see:
- More detections overall
- Cameras 2, 5, and 6 should start producing detections (if they're connected)
- More variety in detected species

### 3. Troubleshooting Cameras 2, 5, and 6

These cameras have never produced detections or haven't in a long time. Check:

#### Camera 2 (wyzecam3-03) - IP: 192.168.88.148
- Verify camera is online: `ping 192.168.88.148`
- Check RTSP stream: `rtsp://192.168.88.148:554/ch0`
- Verify MotionEye can connect to the stream
- Check MotionEye logs for connection errors

#### Camera 5 (wyzecam3-04) - IP: 192.168.88.150
- Verify camera is online: `ping 192.168.88.150`
- Check RTSP stream: `rtsp://192.168.88.150:554/ch0`
- Verify MotionEye can connect to the stream
- Check MotionEye logs for connection errors

#### Camera 6 (WYZECAM3-02) - IP: 192.168.88.97
- Verify camera is online: `ping 192.168.88.97`
- Check RTSP stream: `rtsp://192.168.88.97:554/ch0`
- Last detection was 166 hours ago - camera may be offline
- Check if camera needs to be restarted or reconnected

### 4. Fine-Tuning (If Too Many False Positives)

If you get too many false positives after optimization:

1. **Increase thresholds slightly**:
   - Edit `wildlife-app/motioneye_config/camera-X.conf`
   - Increase `threshold` value by 10-20%
   - Example: `threshold 29952` → `threshold 35000`

2. **Increase minimum motion frames**:
   - Change `minimum_motion_frames 2` → `minimum_motion_frames 3`

3. **Increase event gap**:
   - Change `event_gap 1` → `event_gap 2`

4. **Restart MotionEye** after changes

### 5. Check Webhook Connectivity

Verify webhooks are being sent:

```bash
cd wildlife-app/backend
python check_detections_status.py
```

Or check MotionEye webhook logs:
```bash
# Inside MotionEye container
tail -f /tmp/webhook_debug.log
```

## Expected Improvements

After applying these optimizations, you should see:

1. **2-3x more detections** overall
2. **Better detection of small wildlife** (birds, squirrels, etc.)
3. **Faster response** to motion events
4. **More frequent detections** from active cameras
5. **Cameras 2, 5, 6 should start working** (if they're online and connected)

## Monitoring

Run the analysis script daily to track improvements:

```bash
cd wildlife-app/backend
python analyze_camera_detections.py
```

Look for:
- Increasing detection counts
- More cameras producing detections
- Better species variety
- Reduced "Unknown" and "Blank" detections

## Files Modified

1. **MotionEye Config Files**: All camera configs optimized
   - `wildlife-app/motioneye_config/camera-1.conf` through `camera-8.conf`
   - Backups created as `.backup` files

2. **Smart Detection Service**: Lowered confidence threshold
   - `wildlife-app/backend/services/smart_detection.py`
   - `min_confidence_to_save`: 0.15 → 0.10

## Rollback

If you need to rollback the changes:

1. Restore from backup files:
   ```bash
   cd wildlife-app/motioneye_config
   cp camera-1.conf.backup camera-1.conf
   # Repeat for each camera
   ```

2. Restart MotionEye:
   ```bash
   docker restart wildlife-motioneye
   ```

3. Revert smart_detection.py:
   - Change `min_confidence_to_save` back to `0.15`

