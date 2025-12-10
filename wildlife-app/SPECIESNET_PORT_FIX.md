# SpeciesNet Port 8000 Conflict - Solution

## Problem
When starting SpeciesNet server, you get this error:
```
ERROR: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000): 
only one usage of each socket address (protocol/network address/port) is normally permitted
```

This means **port 8000 is already in use** by another process (likely another SpeciesNet instance).

## Quick Solution

### Option 1: Stop Existing SpeciesNet Server (Recommended)

Use the provided script:
```batch
scripts\stop-speciesnet.bat
```

Or manually:
```batch
REM Find and kill process using port 8000
for /f "tokens=5" %a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /PID %a /F
```

### Option 2: Check if SpeciesNet is Already Running

If SpeciesNet is already running and working, you don't need to start it again!

Test if it's working:
```batch
curl http://localhost:8000/health
```

Or check in your browser:
```
http://localhost:8000/docs
```

If it's working, **just use the existing instance** - no need to restart!

### Option 3: Use a Different Port

If you need to run multiple instances, change the port:

1. Edit `wildlife-app/backend/speciesnet_server.py`:
   ```python
   uvicorn.run(app, host="0.0.0.0", port=8002)  # Changed from 8000
   ```

2. Update `wildlife-app/backend/config.py`:
   ```python
   SPECIESNET_URL = os.getenv("SPECIESNET_URL", "http://localhost:8002")
   ```

3. Update `.env` file:
   ```
   SPECIESNET_URL=http://localhost:8002
   ```

## Prevention

### Check Before Starting

Before starting SpeciesNet, check if port 8000 is free:
```batch
netstat -ano | findstr :8000
```

If you see output, port 8000 is in use.

### Use the Control Scripts

Use the provided scripts to manage SpeciesNet:

**Stop SpeciesNet:**
```batch
scripts\stop-speciesnet.bat
```

**Start SpeciesNet:**
```batch
scripts\start-speciesnet.bat
```

The start script will automatically check if port 8000 is available before starting.

## Common Causes

1. **Previous SpeciesNet instance didn't close properly**
   - Solution: Stop it using the script above

2. **Multiple terminal windows running SpeciesNet**
   - Solution: Close all terminals and restart only one

3. **SpeciesNet started as a service/background process**
   - Solution: Check Task Manager for Python processes

4. **Another application using port 8000**
   - Solution: Change SpeciesNet to a different port (see Option 3)

## Verify SpeciesNet is Working

After starting SpeciesNet, verify it's working:

1. **Check health endpoint:**
   ```batch
   curl http://localhost:8000/health
   ```

2. **Check API docs:**
   Open browser: `http://localhost:8000/docs`

3. **Check logs:**
   You should see:
   ```
   INFO: [OK] SpeciesNet server ready - model loaded successfully
   ```

## Integration with Backend

The backend automatically checks for SpeciesNet at startup. If SpeciesNet is already running on port 8000, the backend will connect to it automatically.

You don't need to restart SpeciesNet every time you restart the backend - they can run independently!

