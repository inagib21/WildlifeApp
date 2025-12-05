# Wildlife App Control Scripts

This folder contains scripts for managing the Wildlife App services.

## 🚀 Quick Start

**Double-click:** `control.bat`

This opens an interactive menu where you can:
- Start all services
- Stop all services
- Restart all services
- Check service status

## Available Scripts

- **`control.bat`** ⭐ **MAIN SCRIPT**
  - Interactive menu with all control options
  - Starts: Docker, SpeciesNet, Backend
  - Stops: All services cleanly
  - Status: Health checks for all services

- **`start-backend-only.bat`** (Optional)
  - Quick script to start only the backend server
  - Useful for debugging backend issues

## What the Script Does

### Start Services:
1. ✅ Checks Docker is running
2. ✅ Starts Docker services (PostgreSQL & MotionEye)
3. ✅ Verifies Python virtual environment exists
4. ✅ Starts SpeciesNet server (port 8000)
5. ✅ Starts Backend server (port 8001)
6. ✅ Runs health check automatically

### Stop Services:
1. ✅ Stops Docker containers
2. ✅ Stops SpeciesNet server (port 8000)
3. ✅ Stops Backend server (port 8001)
4. ✅ Cleans up all processes

### Status Check:
1. ✅ Checks Docker container status
2. ✅ Checks if service processes are running
3. ✅ Checks if ports are listening
4. ✅ Tests HTTP health endpoints
5. ✅ Shows color-coded status

## Service URLs

After starting services, access:
- **Backend API:** http://localhost:8001
- **Backend Docs:** http://localhost:8001/docs
- **SpeciesNet Server:** http://localhost:8000
- **MotionEye:** http://localhost:8765

## Troubleshooting

### Scripts can't find wildlife-app directory
- Make sure you're running scripts from the `scripts/` folder
- Verify the project structure: `Wildlife/scripts/` and `Wildlife/wildlife-app/`

### Services won't start
- Check Docker Desktop is running
- Verify Python venv exists at `wildlife-app/backend/venv/`
- Check ports 8000 and 8001 are not in use by other applications

### Health checks fail
- Services may need 10-15 seconds to fully start
- Check the service windows for error messages
- Verify Docker containers are running: `docker ps`

### API endpoints return network errors
- Backend may be starting or crashed - check the Backend window for errors
- Verify backend is running: `http://localhost:8001/health`
- Check for validation errors in backend logs - invalid data is now handled gracefully
- If issues persist, restart the backend using `start-backend-only.bat`