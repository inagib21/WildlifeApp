@echo off
setlocal enabledelayedexpansion
title Wildlife App - Start All Services (Fixed)

REM Change to project root
cd /d "%~dp0.."

echo ========================================
echo   Wildlife App - Starting All Services
echo ========================================
echo.

REM Step 1: Check Docker
echo [1/5] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Docker is not installed or not in PATH!
    echo   Please install Docker Desktop and start it
    pause
    exit /b 1
)
docker ps >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Docker daemon is not running!
    echo   Please start Docker Desktop
    pause
    exit /b 1
)
echo   [OK] Docker is running

REM Step 2: Start Docker services
echo.
echo [2/5] Starting Docker services (MotionEye + PostgreSQL)...
cd wildlife-app
docker-compose down >nul 2>&1
timeout /t 2 /nobreak >nul
docker-compose up -d
if errorlevel 1 (
    echo   [ERROR] Failed to start Docker containers
    cd ..
    pause
    exit /b 1
)
echo   [OK] Docker containers started
cd ..
timeout /t 5 /nobreak >nul

REM Step 3: Check Python venv
echo.
echo [3/5] Checking Python environment...
set "BACKEND_DIR=%CD%\wildlife-app\backend"
if not exist "%BACKEND_DIR%\venv\Scripts\python.exe" (
    echo   [ERROR] Python virtual environment not found!
    echo   Expected: %BACKEND_DIR%\venv\Scripts\python.exe
    echo.
    echo   Creating virtual environment...
    cd "%BACKEND_DIR%"
    python -m venv venv
    if errorlevel 1 (
        echo   [ERROR] Failed to create venv
        pause
        exit /b 1
    )
    echo   [OK] Virtual environment created
    echo   Installing dependencies...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    if errorlevel 1 (
        echo   [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
    cd ..\..
)
echo   [OK] Python venv found

REM Step 4: Kill any existing processes on ports
echo.
echo [4/5] Clearing ports 8000, 8001, 3000...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8001" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
timeout /t 2 /nobreak >nul
echo   [OK] Ports cleared

REM Step 5: Start services
echo.
echo [5/5] Starting services...
echo.

REM Start SpeciesNet
echo   Starting SpeciesNet (port 8000)...
start "Wildlife SpeciesNet" cmd /k "cd /d "%BACKEND_DIR%" && title Wildlife SpeciesNet && echo ======================================== && echo   Wildlife SpeciesNet Server && echo   Port: 8000 && echo ======================================== && echo. && venv\Scripts\python.exe -m uvicorn speciesnet_server:app --host 0.0.0.0 --port 8000 && echo. && echo Press any key to close... && pause >nul"
timeout /t 5 /nobreak >nul

REM Start Backend
echo   Starting Backend (port 8001)...
start "Wildlife Backend" cmd /k "cd /d "%BACKEND_DIR%" && title Wildlife Backend && echo ======================================== && echo   Wildlife Backend Server && echo   Port: 8001 && echo ======================================== && echo. && venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001 && echo. && echo Press any key to close... && pause >nul"
timeout /t 5 /nobreak >nul

REM Start Frontend
echo   Starting Frontend (port 3000)...
set "FRONTEND_DIR=%CD%\wildlife-app"
start "Wildlife Frontend" cmd /k "title Wildlife Frontend && cd /d "%FRONTEND_DIR%" && echo ======================================== && echo   Wildlife Frontend Server && echo   Port: 3000 && echo ======================================== && echo. && npm run dev && echo. && echo Press any key to close... && pause >nul"
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   Services Started!
echo ========================================
echo.
echo   Waiting 15 seconds for services to initialize...
timeout /t 15 /nobreak >nul

echo.
echo   Checking service status...
echo.

REM Check SpeciesNet
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 5; Write-Host '  SpeciesNet: RUNNING' -ForegroundColor Green } catch { Write-Host '  SpeciesNet: NOT RUNNING (check window for errors)' -ForegroundColor Red }" 2>nul

REM Check Backend
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8001/health' -UseBasicParsing -TimeoutSec 5; Write-Host '  Backend: RUNNING' -ForegroundColor Green } catch { Write-Host '  Backend: NOT RUNNING (check window for errors)' -ForegroundColor Red }" 2>nul

REM Check Frontend
netstat -ano 2>nul | findstr ":3000" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo   Frontend: NOT RUNNING (check window for errors)
) else (
    echo   Frontend: RUNNING
)

echo.
echo   Service URLs:
echo     - Frontend: http://localhost:3000
echo     - Backend API: http://localhost:8001
echo     - API Docs: http://localhost:8001/docs
echo     - SpeciesNet: http://localhost:8000
echo     - MotionEye: http://localhost:8765
echo.
echo   If services are not running, check the service windows for error messages.
echo.
pause

