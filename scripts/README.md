# Wildlife App Control Script

This folder contains a single control script for managing all Wildlife App services.

## 🚀 Quick Start

**Double-click:** `control.bat`

This opens a menu where you can:
- Start all services
- Stop all services
- Check service health/status

## Available Options

- **`control.bat`** ⭐ **MAIN SCRIPT**
  - Interactive menu with Start/Stop/Health Check options
  - Starts all services: SpeciesNet, Backend, Frontend, Docker
  - Stops all services cleanly
  - Health check verifies all services are running and responding

## Usage

Simply double-click `control.bat` and choose an option from the menu.

## What the Scripts Do

### What `start.bat` Does:
1. ✅ Checks Docker is running
2. ✅ Starts Docker services (PostgreSQL & MotionEye)
3. ✅ Verifies Python virtual environment exists
4. ✅ Starts SpeciesNet server (port 8000)
5. ✅ Starts Backend server (port 8001)
6. ✅ Starts Frontend server (port 3000)
7. ✅ Checks service status and shows URLs

### What `stop.bat` Does:
1. ✅ Stops Docker containers
2. ✅ Stops SpeciesNet server (port 8000)
3. ✅ Stops Backend server (port 8001)
4. ✅ Stops Frontend server (port 3000)
5. ✅ Cleans up all processes and ports

## Service URLs

After starting services, access:
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8001
- **Backend Docs:** http://localhost:8001/docs
- **SpeciesNet Server:** http://localhost:8000
- **MotionEye:** http://localhost:8765

## Troubleshooting

### Scripts can't find wildlife-app directory
- Make sure you're running scripts from the `scripts/` folder
- Verify the project structure: `Wildlife/scripts/` and `Wildlife/wildlife-app/`

### Windows won't run scripts
- Right-click script → Properties → Unblock (if blocked)
- Or run from Command Prompt: `cd scripts && start.bat` or `cd scripts && stop.bat`

### Services won't start
- Check that Docker Desktop is installed and running
- Verify Python and Node.js are in your PATH
- Check the service windows for error messages
- Ensure all backend modules exist (config.py, database.py, models.py, services/, utils/, routers/)

### Network Error in Frontend
- Wait 10-15 seconds after starting services for backend to fully initialize
- Check backend window for error messages
- Verify backend is accessible: http://localhost:8001/health
- Check browser console for detailed error messages

