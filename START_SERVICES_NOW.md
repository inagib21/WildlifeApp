# Quick Start Guide - All Services

## Current Status
✅ **SpeciesNet**: RUNNING on port 8000
❌ **Backend**: Starting...
❌ **MotionEye**: Requires Docker Desktop

## Steps to Start Everything

### 1. Start Docker Desktop (Required for MotionEye)
- Open Docker Desktop application
- Wait for it to fully start (whale icon in system tray)
- This is required for MotionEye to run

### 2. Backend Should Be Starting
- A new window should have opened for the Backend
- If not, run this command:
```batch
cd C:\Users\Edwin\Documents\Wildlife\wildlife-app\backend
start "Wildlife Backend" cmd /k "cd /d %CD% && title Wildlife Backend && venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001"
```

### 3. Start Frontend (if needed)
```batch
cd C:\Users\Edwin\Documents\Wildlife\wildlife-app
start "Wildlife Frontend" cmd /k "npm run dev"
```

### 4. Start MotionEye (After Docker Desktop is running)
```batch
cd C:\Users\Edwin\Documents\Wildlife\wildlife-app
docker-compose up -d
```

## OR Use the Control Script
Simply run:
```batch
scripts\control.bat
```
Then choose option [1] to start all services.

## Quick Restart Script
If services are stuck, use:
```batch
scripts\quick-restart.bat
```

## Verify Everything is Running

### Check Health Endpoints:
- SpeciesNet: http://localhost:8000/health
- Backend: http://localhost:8001/health
- MotionEye: http://localhost:8765
- Frontend: http://localhost:3000

### Or use the status check:
```batch
scripts\control.bat
```
Choose option [4] to check service status.

## Service URLs
- Frontend: http://localhost:3000
- Backend API: http://localhost:8001
- API Docs: http://localhost:8001/docs
- SpeciesNet: http://localhost:8000
- MotionEye: http://localhost:8765

