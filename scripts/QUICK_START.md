# Quick Start Guide - Get System Running

## 🚀 Fastest Way to Start Everything

**Double-click:** `scripts\start-system.bat`

This will:
1. Check Docker is running
2. Start Docker services (PostgreSQL, MotionEye)
3. Verify Python environment
4. Start SpeciesNet server (port 8000)
5. Start Backend server (port 8001)
6. Start Frontend server (port 3000)
7. Verify all services are running

## 📋 Prerequisites Check

Before starting, make sure you have:

- ✅ **Docker Desktop** - Running and accessible
- ✅ **Python 3.11+** - Installed
- ✅ **Node.js & npm** - Installed
- ✅ **Virtual environment** - Created in `wildlife-app/backend/venv/`

## 🔧 If Services Don't Start

### Backend Not Starting?

1. **Check Python venv:**
   ```bash
   cd wildlife-app/backend
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Check database connection:**
   - Ensure Docker containers are running: `docker ps`
   - Check PostgreSQL is accessible: `docker logs wildlife-postgres`

3. **Check for errors in backend window:**
   - Look for Python import errors
   - Check database connection errors
   - Verify config.py exists

### SpeciesNet Not Starting?

1. **Check for GPU/CPU issues:**
   - Look for "models.common" errors (should be fixed)
   - Check for "Detect" attribute errors (should be fixed)
   - Verify SpeciesNet package is installed: `pip list | findstr speciesnet`

2. **Check logs in SpeciesNet window:**
   - Model loading errors
   - GPU initialization errors

### Frontend Not Starting?

1. **Check Node.js:**
   ```bash
   node --version
   npm --version
   ```

2. **Install dependencies:**
   ```bash
   cd wildlife-app
   npm install
   ```

3. **Check for port conflicts:**
   - Port 3000 might be in use
   - Check: `netstat -ano | findstr :3000`

## 🐛 Common Issues

### "Module not found" errors
- **Fix:** Activate venv and install requirements
  ```bash
   cd wildlife-app/backend
   venv\Scripts\activate
   pip install -r requirements.txt
  ```

### "Database connection failed"
- **Fix:** Start Docker containers
  ```bash
   cd wildlife-app
   docker-compose up -d
  ```

### "Port already in use"
- **Fix:** Stop existing services
  ```bash
   scripts\stop-wildlife-app.bat
  ```

### "Cannot find module 'main'"
- **Fix:** Make sure you're in the backend directory when starting
  - Backend should start from: `wildlife-app/backend/`
  - SpeciesNet should start from: `wildlife-app/backend/`

## ✅ Verify Everything is Working

After starting, check:

1. **Backend:** http://localhost:8001/health
   - Should return: `{"status":"healthy"}`

2. **SpeciesNet:** http://localhost:8000/health
   - Should return: `{"status":"healthy","model_loaded":true}`

3. **Frontend:** http://localhost:3000
   - Should show the Wildlife app interface

4. **MotionEye:** http://localhost:8765
   - Should show MotionEye interface

## 📞 Still Not Working?

1. Check all service windows for error messages
2. Check Docker logs: `docker logs wildlife-postgres` and `docker logs wildlife-motioneye`
3. Verify all files exist:
   - `wildlife-app/backend/main.py`
   - `wildlife-app/backend/config.py`
   - `wildlife-app/backend/database.py`
   - `wildlife-app/backend/speciesnet_server.py`

