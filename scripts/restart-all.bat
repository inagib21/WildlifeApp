@echo off
setlocal enabledelayedexpansion
title Wildlife App - Complete Restart

echo ========================================
echo   Wildlife App - Complete Restart
echo ========================================
echo.
echo This will:
echo   1. Stop all services
echo   2. Stop Docker containers
echo   3. Wait for cleanup
echo   4. Start Docker containers
echo   5. Wait for PostgreSQL
echo   6. Start all services
echo.

pause

REM Change to project root
cd /d "%~dp0.."

echo.
echo [1/6] Stopping all services...
taskkill /FI "WINDOWTITLE eq Wildlife SpeciesNet*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Wildlife Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Wildlife Frontend*" /F >nul 2>&1
taskkill /IM node.exe /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8001" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
timeout /t 3 /nobreak >nul
echo   Services stopped

echo.
echo [2/6] Stopping Docker containers...
cd wildlife-app
if exist "docker-compose.yml" (
    docker-compose down
    timeout /t 3 /nobreak >nul
    echo   Docker containers stopped
) else (
    echo   docker-compose.yml not found
)
cd ..

echo.
echo [3/6] Waiting for cleanup...
timeout /t 5 /nobreak >nul

echo.
echo [4/6] Checking Docker...
docker ps >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Docker is not running!
    echo   Please start Docker Desktop and try again.
    pause
    exit /b 1
)
echo   Docker: RUNNING

echo.
echo [5/6] Starting Docker containers...
cd wildlife-app
if exist "docker-compose.yml" (
    docker-compose up -d
    timeout /t 5 /nobreak >nul
    echo   Docker containers started
    echo   Waiting for PostgreSQL to be ready...
    
    REM Wait for PostgreSQL
    set POSTGRES_READY=0
    for /L %%i in (1,1,20) do (
        timeout /t 2 /nobreak >nul
        docker exec wildlife-postgres pg_isready -U postgres >nul 2>&1
        if not errorlevel 1 (
            set POSTGRES_READY=1
            echo   PostgreSQL is ready!
            goto POSTGRES_READY
        )
        echo   Waiting... (attempt %%i/20)
    )
    :POSTGRES_READY
    
    if !POSTGRES_READY!==0 (
        echo   WARNING: PostgreSQL may not be fully ready
        echo   Backend will retry connection
    )
    
    REM Show container status
    echo.
    echo   Container status:
    docker ps --filter "name=wildlife" --format "    {{.Names}}: {{.Status}}" 2>nul
) else (
    echo   ERROR: docker-compose.yml not found!
    pause
    exit /b 1
)
cd ..

echo.
echo [5/6] Starting services...
set "VENV_PYTHON=wildlife-app\backend\venv\Scripts\python.exe"
set "BACKEND_DIR=%CD%\wildlife-app\backend"
set "FRONTEND_DIR=%CD%\wildlife-app"

REM Start SpeciesNet
echo   Starting SpeciesNet (port 8000)...
start "Wildlife SpeciesNet" cmd /k "title Wildlife SpeciesNet && cd /d "%BACKEND_DIR%" && echo ======================================== && echo   Wildlife SpeciesNet Server && echo   Port: 8000 && echo ======================================== && echo. && "%BACKEND_DIR%\venv\Scripts\python.exe" -m uvicorn speciesnet_server:app --host 0.0.0.0 --port 8000 --workers 4 && echo. && echo Press any key to close... && pause >nul"
timeout /t 3 /nobreak >nul

REM Start Backend
echo   Starting Backend (port 8001)...
start "Wildlife Backend" cmd /k "title Wildlife Backend && cd /d "%BACKEND_DIR%" && echo ======================================== && echo   Wildlife Backend Server && echo   Port: 8001 && echo ======================================== && echo. && "%BACKEND_DIR%\venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload && echo. && echo Press any key to close... && pause >nul"
timeout /t 3 /nobreak >nul

REM Start Frontend
echo   Starting Frontend (port 3000)...
start "Wildlife Frontend" cmd /k "title Wildlife Frontend && cd /d "%FRONTEND_DIR%" && echo ======================================== && echo   Wildlife Frontend Server && echo   Port: 3000 && echo ======================================== && echo. && npm run dev && echo. && echo Press any key to close... && pause >nul"
timeout /t 3 /nobreak >nul

echo.
echo [6/6] Waiting for services to initialize...
echo   (This may take 15-20 seconds)
timeout /t 10 /nobreak >nul

echo.
echo ========================================
echo   Restart Complete!
echo ========================================
echo.
echo Checking service status...
echo.

powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 5; Write-Host 'SpeciesNet: RUNNING' -ForegroundColor Green } catch { Write-Host 'SpeciesNet: Starting...' -ForegroundColor Yellow }" 2>nul
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8001/health' -UseBasicParsing -TimeoutSec 5; Write-Host 'Backend:    RUNNING' -ForegroundColor Green } catch { Write-Host 'Backend:    Starting...' -ForegroundColor Yellow }" 2>nul
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:3000' -UseBasicParsing -TimeoutSec 5; Write-Host 'Frontend:   RUNNING' -ForegroundColor Green } catch { Write-Host 'Frontend:   Starting...' -ForegroundColor Yellow }" 2>nul

echo.
echo ========================================
echo   Service URLs:
echo ========================================
echo   Frontend:   http://localhost:3000
echo   Backend:    http://localhost:8001
echo   Backend API: http://localhost:8001/docs
echo   SpeciesNet: http://localhost:8000
echo   MotionEye:  http://localhost:8765
echo.
echo If services show as "Starting...", wait 10-15 more seconds
echo and check the service windows for any errors.
echo.
pause

