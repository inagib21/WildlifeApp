# Detection Status Check

## Current Status
- **Last Detection**: 7 minutes ago (Detection #147593)
- **Webhook Status**: Working (1 successful webhook in last hour)
- **Issue**: Some webhooks failing with "Empty webhook payload"

## Troubleshooting Steps

### 1. Check if cameras are detecting motion
- Verify cameras are active and recording
- Check MotionEye interface for recent motion events
- Ensure cameras have motion detection enabled

### 2. Check webhook configuration
- Verify MotionEye webhook URLs are correct
- Check if webhook command is executing properly
- Review MotionEye logs for webhook errors

### 3. Check real-time updates
- Open browser console and check for SSE connection errors
- Verify `/events/detections` endpoint is accessible
- Check if EventManager is running in backend

### 4. Verify backend is processing
- Check backend logs for webhook processing
- Verify SpeciesNet service is responding
- Check database for new detections

## Quick Commands

```bash
# Check recent detections
cd wildlife-app/backend
python check_detections_status.py

# Check backend logs (if running in terminal)
# Look for webhook processing messages

# Check MotionEye logs (if using Docker)
docker logs wildlife-motioneye | grep webhook
```

## Next Steps
1. Wait for next motion event to see if it processes correctly
2. Check camera motion detection sensitivity settings
3. Verify webhook URLs in MotionEye camera configs
4. Check if SpeciesNet service is responding to requests

