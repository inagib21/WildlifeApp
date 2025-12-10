@echo off
setlocal enabledelayedexpansion
title Wildlife App Control Center

REM Change to project root
cd /d "%~dp0.."

:MAIN_MENU
cls
echo ========================================
echo   Wildlife App Control Center
echo ========================================
echo.
echo [1] Start All Services
echo [2] Stop All Services
echo [3] Restart All Services
echo [4] Check Service Status
echo [5] Exit
echo.
set /p choice="Enter your choice (1-5): "

if "%choice%"=="1" goto START_SERVICES
if "%choice%"=="2" goto STOP_SERVICES
if "%choice%"=="3" goto RESTART_ALL
if "%choice%"=="4" goto CHECK_STATUS
if "%choice%"=="5" goto EXIT
goto MAIN_MENU

:START_SERVICES
cls
echo ========================================
echo   Starting All Services
echo ========================================
echo.

REM Check Docker
echo [1/7] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Docker is not installed or not in PATH!
    echo   Please install Docker Desktop and start it
    pause
    goto MAIN_MENU
)
docker ps >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Docker daemon is not running!
    echo   Please start Docker Desktop
    pause
    goto MAIN_MENU
)
echo   [OK] Docker is running

REM Start Docker services
echo.
echo [2/7] Starting Docker services (MotionEye + PostgreSQL)...
if not exist "wildlife-app\docker-compose.yml" (
    echo   [ERROR] docker-compose.yml not found!
    pause
    goto MAIN_MENU
)
cd wildlife-app
docker-compose down >nul 2>&1
timeout /t 2 /nobreak >nul
docker-compose up -d
if errorlevel 1 (
    echo   [ERROR] Failed to start Docker containers
    pause
    cd ..
    goto MAIN_MENU
)
echo   [OK] Docker containers started
cd ..
timeout /t 5 /nobreak >nul

REM Check and setup Python venv
echo.
echo [3/7] Checking Python environment...
set "PROJECT_ROOT=%CD%"
set "BACKEND_DIR=%PROJECT_ROOT%\wildlife-app\backend"
if not exist "%BACKEND_DIR%\venv\Scripts\python.exe" (
    echo   [WARN] Python virtual environment not found!
    echo   Expected: %BACKEND_DIR%\venv\Scripts\python.exe
    echo.
    echo   Creating virtual environment...
    cd "%BACKEND_DIR%"
    python -m venv venv
    if errorlevel 1 (
        echo   [ERROR] Failed to create venv
        echo   Please ensure Python is installed and in PATH
        pause
        cd "%PROJECT_ROOT%"
        goto MAIN_MENU
    )
    echo   [OK] Virtual environment created
    echo   Installing dependencies...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    if errorlevel 1 (
        echo   [ERROR] Failed to install dependencies
        pause
        cd "%PROJECT_ROOT%"
        goto MAIN_MENU
    )
    echo   [OK] Dependencies installed
    cd "%PROJECT_ROOT%"
)
echo   [OK] Python venv found

REM Clear ports
echo.
echo [4/7] Clearing ports 8000, 8001, 3000...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8001" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
timeout /t 2 /nobreak >nul
echo   [OK] Ports cleared

REM Start SpeciesNet
echo.
echo [5/7] Starting SpeciesNet Server (port 8000)...
REM Check if port 8000 is already in use
netstat -ano 2>nul | findstr ":8000" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo   [WARN] Port 8000 is already in use, stopping existing process...
    for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000" ^| findstr "LISTENING"') do (
        taskkill /F /PID %%a >nul 2>&1
        echo   Stopped existing process on port 8000
    )
    timeout /t 2 /nobreak >nul
)
start "Wildlife SpeciesNet" cmd /k "cd /d "%BACKEND_DIR%" && title Wildlife SpeciesNet && echo ======================================== && echo   Wildlife SpeciesNet Server && echo   Port: 8000 && echo ======================================== && echo. && venv\Scripts\python.exe -m uvicorn speciesnet_server:app --host 0.0.0.0 --port 8000 && echo. && echo Press any key to close... && pause >nul"
timeout /t 5 /nobreak >nul

REM Start Backend
echo.
echo [6/7] Starting Backend Server (port 8001)...
REM Check if port 8001 is already in use
netstat -ano 2>nul | findstr ":8001" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo   [WARN] Port 8001 is already in use, stopping existing process...
    for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8001" ^| findstr "LISTENING"') do (
        taskkill /F /PID %%a >nul 2>&1
        echo   Stopped existing process on port 8001
    )
    timeout /t 2 /nobreak >nul
)
start "Wildlife Backend" cmd /k "cd /d "%BACKEND_DIR%" && title Wildlife Backend && echo ======================================== && echo   Wildlife Backend Server && echo   Port: 8001 && echo ======================================== && echo. && venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001 && echo. && echo Press any key to close... && pause >nul"
timeout /t 5 /nobreak >nul

REM Start Frontend
echo.
echo [7/7] Starting Frontend Server (port 3000)...
where npm >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] npm not found in PATH!
    echo   Please install Node.js from https://nodejs.org/
    pause
    goto MAIN_MENU
)
if not exist "wildlife-app\package.json" (
    echo   [ERROR] package.json not found!
    pause
    goto MAIN_MENU
)
set "FRONTEND_DIR=%PROJECT_ROOT%\wildlife-app"
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

REM Check MotionEye
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8765' -UseBasicParsing -TimeoutSec 5; Write-Host '  MotionEye: RUNNING' -ForegroundColor Green } catch { Write-Host '  MotionEye: NOT RUNNING (check Docker)' -ForegroundColor Yellow }" 2>nul

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
if "%1"=="from_restart" (
    exit /b 0
) else (
    pause
    goto MAIN_MENU
)

:STOP_SERVICES
cls
echo ========================================
echo   Stopping All Services
echo ========================================
echo.

REM Stop Docker containers
echo [1/4] Stopping Docker containers...
cd wildlife-app
docker-compose down >nul 2>&1
cd ..
echo   [OK] Docker containers stopped

REM Stop SpeciesNet
echo.
echo [2/4] Stopping SpeciesNet (port 8000)...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo   Stopped process on port 8000
)
taskkill /F /FI "WINDOWTITLE eq Wildlife SpeciesNet*" >nul 2>&1
echo   [OK] SpeciesNet stopped

REM Stop Backend
echo.
echo [3/4] Stopping Backend (port 8001)...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8001" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo   Stopped process on port 8001
)
taskkill /F /FI "WINDOWTITLE eq Wildlife Backend*" >nul 2>&1
echo   [OK] Backend stopped

REM Stop Frontend
echo.
echo [4/4] Stopping Frontend (port 3000)...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo   Stopped process on port 3000
)
taskkill /F /FI "WINDOWTITLE eq Wildlife Frontend*" >nul 2>&1
echo   [OK] Frontend stopped

echo.
echo   All services have been stopped.
echo.
if "%1"=="from_restart" (
    exit /b 0
) else (
    pause
    goto MAIN_MENU
)

:RESTART_ALL
cls
echo ========================================
echo   Restarting All Services
echo ========================================
echo.
echo   Stopping services first...
call :STOP_SERVICES from_restart
timeout /t 3 /nobreak >nul
echo.
echo   Starting services...
call :START_SERVICES from_restart
echo.
echo   Restart complete!
pause
goto MAIN_MENU

:CHECK_STATUS
cls
echo ========================================
echo   Service Status Check
echo ========================================
echo.
echo   Checking all services...
echo.

REM Check Docker
echo [Docker Services]
docker ps --filter "name=wildlife" --format "  {{.Names}}: {{.Status}}" 2>nul
if errorlevel 1 (
    echo   [ERROR] Docker not running or containers not found
) else (
    docker ps --filter "name=wildlife" --format "  {{.Names}}: {{.Status}}" 2>nul | findstr /V "^$" >nul
    if errorlevel 1 (
        echo   [WARN] No Wildlife containers found
    ) else (
        echo   [OK] Docker containers running
    )
)
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8765' -UseBasicParsing -TimeoutSec 5; Write-Host '  MotionEye: ACCESSIBLE' -ForegroundColor Green } catch { Write-Host '  MotionEye: NOT ACCESSIBLE' -ForegroundColor Red }" 2>nul
echo.

REM Check SpeciesNet
echo [SpeciesNet - Port 8000]
netstat -ano 2>nul | findstr ":8000" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo   [ERROR] Not listening on port 8000
) else (
    echo   [OK] Port 8000 is listening
)
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 5; $json = $r.Content | ConvertFrom-Json; Write-Host '  Health: PASSED' -ForegroundColor Green; if ($json.model_loaded) { Write-Host '  Model: LOADED' -ForegroundColor Green } else { Write-Host '  Model: NOT LOADED' -ForegroundColor Yellow } } catch { Write-Host '  Health: FAILED' -ForegroundColor Red }" 2>nul
echo.

REM Check Backend
echo [Backend - Port 8001]
netstat -ano 2>nul | findstr ":8001" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo   [ERROR] Not listening on port 8001
) else (
    echo   [OK] Port 8001 is listening
)
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8001/health' -UseBasicParsing -TimeoutSec 5; Write-Host '  Health: PASSED' -ForegroundColor Green; Write-Host '  API Docs: http://localhost:8001/docs' -ForegroundColor Cyan } catch { Write-Host '  Health: FAILED' -ForegroundColor Red }" 2>nul
echo.

REM Check Frontend
echo [Frontend - Port 3000]
netstat -ano 2>nul | findstr ":3000" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo   [ERROR] Not listening on port 3000
) else (
    echo   [OK] Port 3000 is listening
    powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:3000' -UseBasicParsing -TimeoutSec 5; Write-Host '  Status: RESPONDING' -ForegroundColor Green } catch { Write-Host '  Status: NOT RESPONDING' -ForegroundColor Yellow }" 2>nul
)
echo.
echo ========================================
echo   Service URLs:
echo     - Frontend: http://localhost:3000
echo     - Backend API: http://localhost:8001
echo     - API Docs: http://localhost:8001/docs
echo     - SpeciesNet: http://localhost:8000
echo     - MotionEye: http://localhost:8765
echo ========================================
echo.
pause
goto MAIN_MENU

:EXIT
cls
echo.
echo   Exiting Wildlife App Control Center...
echo.
timeout /t 2 /nobreak >nul
exit /b 0
