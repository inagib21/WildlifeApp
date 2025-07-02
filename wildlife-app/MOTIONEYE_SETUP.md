# MotionEye Integration Setup

This guide will help you set up MotionEye for wildlife monitoring with RTSP camera streams.

## Prerequisites

1. Docker and Docker Compose installed
2. RTSP camera(s) accessible on your network
3. Node.js and npm (for frontend)

## Quick Start

1. **Start MotionEye and Backend:**
   ```bash
   # Run the setup script
   start-motioneye.bat
   
   # Or manually:
   docker-compose up motioneye -d
   docker-compose up backend -d
   ```

2. **Start Frontend:**
   ```bash
   cd wildlife-app
   npm run dev
   ```

## Access Points

- **MotionEye Web Interface:** http://localhost:8765
- **Backend API:** http://localhost:8000
- **Frontend:** http://localhost:3000

## Adding Cameras

### Method 1: Through MotionEye Web Interface
1. Go to http://localhost:8765
2. Click "Add Camera"
3. Select "Network Camera"
4. Enter your RTSP URL (e.g., `rtsp://192.168.1.100:554/stream`)
5. Configure settings as needed
6. Save

### Method 2: Through Backend API
```bash
curl -X POST http://localhost:8000/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Wildlife Camera 1",
    "url": "rtsp://192.168.1.100:554/stream",
    "width": 1280,
    "height": 720,
    "framerate": 30
  }'
```

## Camera Configuration

### RTSP URL Format
- **Generic:** `rtsp://username:password@ip:port/stream`
- **Example:** `rtsp://admin:password@192.168.1.100:554/h264Preview_01_main`

### Common Camera Brands
- **Hikvision:** `rtsp://admin:password@ip:554/Streaming/Channels/101`
- **Dahua:** `rtsp://admin:password@ip:554/cam/realmonitor?channel=1&subtype=0`
- **Axis:** `rtsp://admin:password@ip:554/axis-media/media.amp`

## Troubleshooting

### MotionEye Not Starting
```bash
# Check logs
docker-compose logs motioneye

# Restart container
docker-compose restart motioneye
```

### Camera Stream Not Working
1. Verify RTSP URL is accessible
2. Check camera credentials
3. Ensure camera supports RTSP
4. Test with VLC player first

### Backend Connection Issues
```bash
# Check backend logs
docker-compose logs backend

# Test API health
curl http://localhost:8000/health
```

## File Structure

```
wildlife-app/
├── docker-compose.yml          # MotionEye and Backend services
├── backend/                    # FastAPI backend
├── motioneye_config/          # MotionEye configuration
├── motioneye_media/           # Recorded videos and images
└── wildlife-app/              # Next.js frontend
```

## API Endpoints

- `GET /cameras` - List all cameras
- `POST /cameras` - Add new camera
- `GET /stream/{camera_id}` - Get camera stream info
- `GET /motioneye/status` - Check MotionEye status
- `GET /system` - System health and status

## Next Steps

1. Configure motion detection settings
2. Set up recording schedules
3. Configure storage settings
4. Add species detection integration
5. Set up alerts and notifications 