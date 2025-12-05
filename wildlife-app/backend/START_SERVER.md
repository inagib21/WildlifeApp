# Starting the Server

## Quick Start

### Option 1: Using the Control Script (Recommended)
```batch
cd C:\Users\Edwin\Documents\Wildlife\scripts
control.bat
```
Then select option [1] to start all services.

### Option 2: Start Backend Only
```batch
cd C:\Users\Edwin\Documents\Wildlife\scripts
start-backend-only.bat
```

### Option 3: Manual Start
```batch
cd C:\Users\Edwin\Documents\Wildlife\wildlife-app\backend
venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## Verify Server is Running

1. **Check the server window** - You should see:
   ```
   ========================================
     Wildlife Backend Server
     Port: 8001
   ========================================
   INFO:     Uvicorn running on http://0.0.0.0:8001
   ```

2. **Test the health endpoint:**
   - Open browser: http://localhost:8001/health
   - Or use PowerShell:
     ```powershell
     Invoke-WebRequest -Uri "http://localhost:8001/health"
     ```

3. **Check API documentation:**
   - Open browser: http://localhost:8001/docs

## Troubleshooting

### Port Already in Use
If port 8001 is already in use:
```batch
netstat -ano | findstr ":8001"
taskkill /F /PID <PID_NUMBER>
```

### Import Errors
If you see import errors:
1. Make sure you're in the `wildlife-app\backend` directory
2. Verify virtual environment is activated
3. Check that all dependencies are installed: `venv\Scripts\pip.exe install -r requirements.txt`

### Database Connection Errors
Database connection warnings are expected if PostgreSQL isn't running. The API will still work, but database features won't be available.

## Service URLs

Once running:
- **Backend API:** http://localhost:8001
- **API Documentation:** http://localhost:8001/docs
- **Health Check:** http://localhost:8001/health
- **System Status:** http://localhost:8001/system

