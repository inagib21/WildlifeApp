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
echo [1/6] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Docker is not installed or not in PATH!
    echo   Please install Docker Desktop
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
echo [2/6] Starting Docker services...
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

REM Check Python venv
echo.
echo [3/6] Checking Python environment...
if not exist "wildlife-app\backend\venv\Scripts\python.exe" (
    echo   [ERROR] Python virtual environment not found!
    echo   Expected: wildlife-app\backend\venv\Scripts\python.exe
    pause
    goto MAIN_MENU
)
echo   [OK] Python venv found

REM Set backend directory path (before changing directories)
set "PROJECT_ROOT=%CD%"
set "BACKEND_DIR=%PROJECT_ROOT%\wildlife-app\backend"
set "PYTHON_EXE=%BACKEND_DIR%\venv\Scripts\python.exe"

REM Start SpeciesNet
echo.
echo [4/6] Starting SpeciesNet Server (port 8000)...
netstat -ano 2>nul | findstr ":8000" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo   [INFO] Port 8000 already in use, stopping existing process...
    for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
    timeout /t 2 /nobreak >nul
)
start "Wildlife SpeciesNet" cmd /k "cd /d "%BACKEND_DIR%" && title Wildlife SpeciesNet && echo ======================================== && echo   Wildlife SpeciesNet Server && echo   Port: 8000 && echo ======================================== && echo. && venv\Scripts\python.exe -m uvicorn speciesnet_server:app --host 0.0.0.0 --port 8000 --workers 4 && echo. && echo Press any key to close... && pause >nul"
timeout /t 3 /nobreak >nul

REM Start Backend
echo.
echo [5/6] Starting Backend Server (port 8001)...
netstat -ano 2>nul | findstr ":8001" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo   [INFO] Port 8001 already in use, stopping existing process...
    for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8001" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
    timeout /t 2 /nobreak >nul
)
start "Wildlife Backend" cmd /k "cd /d "%BACKEND_DIR%" && title Wildlife Backend && echo ======================================== && echo   Wildlife Backend Server && echo   Port: 8001 && echo ======================================== && echo. && venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload && echo. && echo Press any key to close... && pause >nul"
timeout /t 5 /nobreak >nul

REM Start Frontend
echo.
echo [6/6] Starting Frontend Server...
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
set "FRONTEND_DIR=%CD%\wildlife-app"
netstat -ano 2>nul | findstr ":3000" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo   [INFO] Port 3000 already in use, stopping existing process...
    for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
    timeout /t 2 /nobreak >nul
)
start "Wildlife Frontend" cmd /k "title Wildlife Frontend && cd /d "%FRONTEND_DIR%" && echo ======================================== && echo   Wildlife Frontend Server && echo   Port: 3000 && echo ======================================== && echo. && npm run dev && echo. && echo Press any key to close... && pause >nul"
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   Services Starting...
echo ========================================
echo.
echo   SpeciesNet: Starting (port 8000)
echo   Backend: Starting (port 8001)
echo   Frontend: Starting (port 3000)
echo.
echo   Waiting for services to initialize...
timeout /t 10 /nobreak >nul

echo.
echo   Checking service status...
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 5; Write-Host '  SpeciesNet: RUNNING' -ForegroundColor Green } catch { Write-Host '  SpeciesNet: Starting...' -ForegroundColor Yellow }" 2>nul
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8001/health' -UseBasicParsing -TimeoutSec 5; Write-Host '  Backend: RUNNING' -ForegroundColor Green } catch { Write-Host '  Backend: Starting...' -ForegroundColor Yellow }" 2>nul
netstat -ano 2>nul | findstr ":3000" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo   Frontend: Starting...
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
echo [1/3] Stopping Docker containers...
cd wildlife-app
docker-compose down >nul 2>&1
cd ..
echo   [OK] Docker containers stopped

REM Stop Python processes
echo.
echo [2/3] Stopping Python services...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo   Stopped process on port 8000
)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8001" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo   Stopped process on port 8001
)

REM Stop any remaining Python/uvicorn processes
taskkill /F /FI "WINDOWTITLE eq Wildlife SpeciesNet*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Wildlife Backend*" >nul 2>&1
echo   [OK] Python services stopped

REM Stop Frontend
echo.
echo [3/3] Stopping Frontend...
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

REM Check Docker
echo [Docker]
docker ps --filter "name=wildlife" --format "  {{.Names}}: {{.Status}}" 2>nul
if errorlevel 1 (
    echo   [ERROR] Docker not running or containers not found
) else (
    echo   [OK] Docker containers
)
echo.

REM Check SpeciesNet
echo [SpeciesNet - Port 8000]
netstat -ano 2>nul | findstr ":8000" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo   [ERROR] Not listening on port 8000
) else (
    echo   [OK] Port 8000 is listening
)
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 5; Write-Host '  [OK] Health check: PASSED' -ForegroundColor Green } catch { Write-Host '  [ERROR] Health check: FAILED' -ForegroundColor Red }" 2>nul
echo.

REM Check Backend
echo [Backend - Port 8001]
netstat -ano 2>nul | findstr ":8001" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo   [ERROR] Not listening on port 8001
) else (
    echo   [OK] Port 8001 is listening
)
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8001/health' -UseBasicParsing -TimeoutSec 5; Write-Host '  [OK] Health check: PASSED' -ForegroundColor Green } catch { Write-Host '  [ERROR] Health check: FAILED' -ForegroundColor Red }" 2>nul
echo.

REM Check Frontend
echo [Frontend - Port 3000]
netstat -ano 2>nul | findstr ":3000" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo   [ERROR] Not listening on port 3000
) else (
    echo   [OK] Port 3000 is listening
    powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:3000' -UseBasicParsing -TimeoutSec 5; Write-Host '  [OK] Frontend is responding' -ForegroundColor Green } catch { Write-Host '  [WARN] Frontend may still be starting' -ForegroundColor Yellow }" 2>nul
)
echo.

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
