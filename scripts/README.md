# Wildlife App Startup Scripts

This folder contains the Windows batch scripts for managing the Wildlife App services.

## 🚀 Quick Start

**Recommended:** Double-click `wildlife-app-control.bat` for an interactive menu-driven control center.

## Available Scripts

- **`wildlife-app-control.bat`** ⭐ **MAIN SCRIPT**
  - Interactive menu with Start/Stop/Status options
  - Handles all services automatically
  - Best for daily use

- **`stop-wildlife-app.bat`**
  - Quick one-click shutdown for all services
  - Use if you need to stop services quickly without opening the control center

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

