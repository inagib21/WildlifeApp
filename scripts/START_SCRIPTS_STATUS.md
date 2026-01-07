# Start Scripts Status

## ✅ All Start Scripts Still Work!

All start scripts are **fully compatible** with the new AI backend system. The new AI backends (YOLOv11, YOLOv8, CLIP, ViT) automatically initialize when the backend server starts, so **no script changes are needed**.

## Available Start Scripts

### 1. **`control.bat`** ⭐ MAIN SCRIPT (Recommended)
**Location:** `scripts/control.bat`

**Features:**
- Interactive menu with all control options
- Start/Stop/Restart/Status check
- Automatic health checks
- Service management

**What it does:**
1. ✅ Checks Docker is running
2. ✅ Starts Docker services (PostgreSQL & MotionEye)
3. ✅ Verifies Python virtual environment
4. ✅ Starts SpeciesNet server (port 8000) - Optional
5. ✅ Starts Backend server (port 8001) - **Auto-initializes all AI backends**
6. ✅ Starts Frontend server (port 3000)
7. ✅ Runs health checks

**Usage:**
```bash
cd scripts
control.bat
# Select option [1] Start All Services
```

### 2. **`start-all-fixed.bat`**
**Location:** `scripts/start-all-fixed.bat`

**Features:**
- Non-interactive - starts everything automatically
- Clears ports before starting
- Shows service status after startup

**What it does:**
1. ✅ Checks Docker
2. ✅ Starts Docker services
3. ✅ Checks/creates Python venv
4. ✅ Clears ports 8000, 8001, 3000
5. ✅ Starts all services in separate windows
6. ✅ Checks service health

**Usage:**
```bash
cd scripts
start-all-fixed.bat
```

### 3. **`start-backend-only.bat`**
**Location:** `scripts/start-backend-only.bat`

**Features:**
- Quick script to start only the backend
- Useful for debugging backend issues
- Waits for backend to be ready

**What it does:**
1. ✅ Checks Python venv exists
2. ✅ Starts Backend server (port 8001)
3. ✅ Waits for backend to respond
4. ✅ Shows status

**Usage:**
```bash
cd scripts
start-backend-only.bat
```

### 4. **`quick-restart.bat`**
**Location:** `scripts/quick-restart.bat`

**Features:**
- Quick restart of all services
- Stops everything first, then starts

## What Happens When Backend Starts

When the backend server starts, it **automatically**:

1. ✅ Initializes AI Backend Manager
2. ✅ Checks for YOLOv11 (auto-downloads if needed)
3. ✅ Checks for YOLOv8 (auto-downloads if needed)
4. ✅ Checks for CLIP (loads from HuggingFace)
5. ✅ Checks for ViT (loads from HuggingFace)
6. ✅ Checks for SpeciesNet (if server is running)
7. ✅ Creates Ensemble backend (combines all available)
8. ✅ Sets default backend based on config

**You'll see detailed logs like:**
```
============================================================
Initializing AI Backend Manager
============================================================
Configured default backend: ensemble
Checking SpeciesNet backend...
Checking YOLOv11 backend...
  ✓ YOLOv11 backend registered and available (BEST CHOICE)
Checking YOLOv8 backend...
  ✓ YOLOv8 backend registered and available
Checking CLIP backend...
  ✓ CLIP backend registered and available
Checking ViT backend...
  ✓ ViT backend registered and available
...
Backend Summary: 5 available, 1 unavailable
Available backends: yolov11, yolov8, clip, vit, ensemble
============================================================
AI Backend Manager initialized - Default: ensemble
============================================================
```

## Service URLs

After starting, access:
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8001
- **API Docs:** http://localhost:8001/docs
- **AI Backends:** http://localhost:8001/api/ai/backends
- **AI Metrics:** http://localhost:8001/api/ai/metrics
- **SpeciesNet:** http://localhost:8000 (if started)
- **MotionEye:** http://localhost:8765

## Troubleshooting

### Backend Starts But AI Backends Not Available

**Check logs in the Backend window:**
- Look for "Initializing AI Backend Manager" section
- Check which backends show ✓ vs ✗
- Common issues:
  - Missing dependencies (install: `pip install ultralytics transformers torch`)
  - GPU/CUDA issues (will fall back to CPU)
  - Network issues (models download from HuggingFace)

### SpeciesNet Not Available

**This is normal!** SpeciesNet requires a separate server. The other 5 AI backends work independently:
- YOLOv11 ✅
- YOLOv8 ✅
- CLIP ✅
- ViT ✅
- Ensemble ✅

### Port Already in Use

**Fix:** The scripts automatically clear ports, but if issues persist:
```bash
# Manually clear ports
netstat -ano | findstr ":8000"
netstat -ano | findstr ":8001"
netstat -ano | findstr ":3000"
# Kill processes using those ports
taskkill /F /PID <process_id>
```

## Verification

After starting, verify AI backends are working:

1. **Check backend logs** - Look for "AI Backend Manager initialized"
2. **Check API endpoint:**
   ```bash
   curl http://localhost:8001/api/ai/backends
   ```
3. **Run diagnostic:**
   ```bash
   cd wildlife-app/backend
   python check_clip_vit.py
   ```

## Summary

✅ **All start scripts work perfectly with the new AI backend system**

✅ **No script changes needed** - AI backends auto-initialize

✅ **Backward compatible** - Everything still works as before

✅ **Enhanced functionality** - Now includes multiple AI models automatically

The scripts are ready to use! 🚀

