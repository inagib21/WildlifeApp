# Local Backend Setup with SpeciesNet Integration

## Overview
This setup runs the backend locally with GPU support for SpeciesNet, while using Docker for MotionEye and PostgreSQL.

## Architecture
- **MotionEye:** Docker container (handles RTSP streams)
- **PostgreSQL:** Docker container (database)
- **Backend:** Local Python (integrates with SpeciesNet)
- **Frontend:** Local Next.js (React app)
- **SpeciesNet:** Local with GPU support

## Prerequisites
1. Docker and Docker Compose installed
2. Python 3.11 with SpeciesNet environment
3. Node.js and npm
4. RTSP camera(s)

## Step-by-Step Setup

### 1. Start Docker Services
```bash
# Start MotionEye and PostgreSQL
docker-compose up -d
```

### 2. Verify Services
- **MotionEye:** http://localhost:8765
- **PostgreSQL:** localhost:5432
- **Database:** wildlife (user: postgres, password: postgres)

### 3. Start Local Backend
```bash
# Run the startup script
start-local-backend.bat
```

Or manually:
```bash
# Activate SpeciesNet environment
C:\Users\Edwin\Documents\Wildlife\speciesnet_env_py311_clean\Scripts\activate.bat

# Install dependencies
pip install -r backend_local\requirements.txt

# Start backend
cd backend_local
python main.py
```

### 4. Start Frontend
```bash
cd wildlife-app
npm run dev
```

## Access Points
- **MotionEye:** http://localhost:8765
- **Backend API:** http://localhost:8000
- **Frontend:** http://localhost:3000
- **SpeciesNet:** http://localhost:8000 (same as backend)

## Adding Cameras

### Method 1: Through Frontend
1. Go to http://localhost:3000/cameras
2. Click "Add Camera"
3. Enter RTSP URL and settings
4. Camera will be added to both database and MotionEye

### Method 2: Through MotionEye
1. Go to http://localhost:8765
2. Click "Add Camera" → "Network Camera"
3. Configure RTSP URL and settings
4. Camera will be available in frontend

## SpeciesNet Integration

### Automatic Processing
- The backend automatically starts SpeciesNet server
- Images from MotionEye can be processed for species detection
- Results are stored in PostgreSQL database

### Manual Processing
```bash
# Process a single image
curl -X POST http://localhost:8000/process-image \
  -F "file=@path/to/image.jpg" \
  -F "camera_id=1"
```

### API Endpoints
- `GET /detections` - List all detections
- `POST /process-image` - Process image with SpeciesNet
- `GET /system` - System health (includes SpeciesNet status)

## Database Schema

### Cameras Table
- id, name, url, is_active
- MotionEye configuration fields
- Created timestamp

### Detections Table
- id, camera_id, timestamp
- species, confidence, image_path
- prediction_score, detections_json (SpeciesNet data)

## Troubleshooting

### SpeciesNet Not Starting
```bash
# Check if SpeciesNet is installed
python -c "import speciesnet; print('SpeciesNet OK')"

# Start manually
python -m speciesnet.scripts.run_server --port 8000
```

### Database Connection Issues
```bash
# Check PostgreSQL
docker-compose logs postgres

# Test connection
psql -h localhost -U postgres -d wildlife
```

### MotionEye Issues
```bash
# Check MotionEye logs
docker-compose logs motioneye

# Restart MotionEye
docker-compose restart motioneye
```

### Backend Issues
```bash
# Check backend logs
# Look for error messages in console

# Restart backend
# Stop with Ctrl+C and run start-local-backend.bat again
```

## Performance Optimization

### GPU Support
- SpeciesNet runs locally with GPU support
- Ensure CUDA is properly installed
- Check GPU usage with `nvidia-smi`

### Database Optimization
- PostgreSQL runs in Docker with persistent volume
- Consider adding indexes for large datasets
- Monitor disk usage for image storage

### Memory Management
- MotionEye handles video streams
- SpeciesNet processes images as needed
- Monitor system resources

## File Structure
```
wildlife-app/
├── docker-compose.yml          # MotionEye + PostgreSQL
├── backend_local/              # Local backend with SpeciesNet
│   ├── main.py                # FastAPI backend
│   └── requirements.txt       # Python dependencies
├── start-local-backend.bat    # Backend startup script
├── motioneye_media/           # MotionEye recordings
└── wildlife-app/              # Next.js frontend
```

## Next Steps
1. Configure motion detection in MotionEye
2. Set up automatic species detection triggers
3. Add alerting and notifications
4. Implement data visualization and analytics
5. Add user authentication and management 