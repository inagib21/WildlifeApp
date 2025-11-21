# Wildlife App Startup Scripts

This folder contains all the Windows batch and PowerShell scripts for managing the Wildlife App services.

## 🚀 Quick Start

**Recommended:** Double-click `wildlife-app-control.bat` for an interactive menu-driven control center.

## Available Scripts

### Main Scripts

- **`wildlife-app-control.bat`** ⭐ **RECOMMENDED**
  - Interactive menu with Start/Stop/Status options
  - Best for daily use
  - Handles all services automatically

- **`start-wildlife-app.bat`**
  - One-click startup for all services
  - Starts Docker, Backend, and Frontend
  - Opens separate windows for each service

- **`stop-wildlife-app.bat`**
  - One-click shutdown for all services
  - Stops Docker containers and processes

### Alternative Scripts

- **`start-wildlife-app-simple.bat`**
  - Minimal startup script (no Docker checks)
  - Alternative if main script has issues

- **`start-wildlife-app-fixed.bat`**
  - Fixed version that uses Python directly
  - Use if venv path issues occur

- **`stop-wildlife-app.ps1`**
  - PowerShell version of stop script
  - Alternative to batch file

## Usage

All scripts are designed to be run from this `scripts/` folder. They automatically navigate to the correct project directories.

### From Command Line

```batch
cd scripts
wildlife-app-control.bat
```

### From File Explorer

Simply double-click any `.bat` file in this folder.

## What the Scripts Do

### Startup Scripts
1. Check Docker status and start if needed
2. Start Docker services (PostgreSQL & MotionEye)
3. Launch Backend server (FastAPI on port 8001)
4. Launch Frontend server (Next.js on port 3000)

### Stop Scripts
1. Stop Docker containers
2. Kill Backend processes (Python)
3. Kill Frontend processes (Node.js)

## Service URLs

After starting services, access:
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8001
- **Backend Docs:** http://localhost:8001/docs
- **MotionEye:** http://localhost:8765

## Troubleshooting

### Scripts can't find wildlife-app directory
- Make sure you're running scripts from the `scripts/` folder
- Verify the project structure: `Wildlife/scripts/` and `Wildlife/wildlife-app/`

### Windows won't run scripts
- Right-click script → Properties → Unblock (if blocked)
- Or run from Command Prompt: `cd scripts && wildlife-app-control.bat`

### Services won't start
- Check that Docker Desktop is installed and running
- Verify Python and Node.js are in your PATH
- Check the service windows for error messages

