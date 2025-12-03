@echo off
setlocal enabledelayedexpansion
title Wildlife App Control

REM Jump to main menu - skip function definitions
goto MAIN_MENU

:MAIN_MENU
cls
echo ========================================
echo   Wildlife App Control
echo ========================================
echo.
echo [1] Start All Services
echo [2] Stop All Services
echo [3] Restart All Services (Complete Reset)
echo [4] Force Start (Waits for Services)
echo [5] Check Service Status (Health Check)
echo [6] Verify System (Complete Check)
echo [7] Check Docker Status
echo [8] Troubleshooting / Diagnostics
echo [9] Quick Fix Backend
echo [10] Diagnose Backend Issues
echo [11] Diagnose SpeciesNet Issues
echo [12] Exit
echo.
set /p choice="Enter your choice (1-12): "

if "%choice%"=="1" goto START_SERVICES
if "%choice%"=="2" goto STOP_SERVICES
if "%choice%"=="3" goto RESTART_ALL
if "%choice%"=="4" goto FORCE_START
if "%choice%"=="5" goto HEALTH_CHECK
if "%choice%"=="6" goto VERIFY_SYSTEM
if "%choice%"=="7" goto CHECK_DOCKER
if "%choice%"=="8" goto TROUBLESHOOT
if "%choice%"=="9" goto QUICK_FIX
if "%choice%"=="10" goto DIAGNOSE_BACKEND
if "%choice%"=="11" goto DIAGNOSE_SPECIESNET
if "%choice%"=="12" goto EXIT
goto MAIN_MENU

:START_SERVICES
cls
echo ========================================
echo   Starting All Services
echo ========================================
echo.

REM Change to project root
cd /d "%~dp0.."

REM Check Docker
echo [1/6] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Docker is not installed or not in PATH!
    echo   Please install Docker Desktop from https://www.docker.com/products/docker-desktop
    pause
    goto MAIN_MENU
)
docker ps >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Docker daemon is not running!
    echo   Please start Docker Desktop and wait for it to fully start.
    echo   Look for the whale icon in your system tray.
    pause
    goto MAIN_MENU
)
echo   Docker: INSTALLED and RUNNING

REM Start Docker services
echo.
echo [2/6] Starting Docker services...
REM Change to wildlife-app directory where docker-compose.yml is located
if not exist "wildlife-app\docker-compose.yml" (
    echo   ERROR: docker-compose.yml not found!
    echo   Expected: %CD%\wildlife-app\docker-compose.yml
    echo.
    echo   Current directory: %CD%
    if exist "wildlife-app" (
        echo   wildlife-app directory exists
        dir /b wildlife-app\*.yml 2>nul
        dir /b wildlife-app\*.yaml 2>nul
    ) else (
        echo   wildlife-app directory not found!
    )
    pause
    goto MAIN_MENU
)

cd wildlife-app
echo   Using docker-compose.yml from: %CD%
echo   Stopping any existing containers first...
docker-compose down >nul 2>&1
timeout /t 2 /nobreak >nul

echo   Starting PostgreSQL and MotionEye containers...
docker-compose up -d
if errorlevel 1 (
    echo   ERROR: Failed to start Docker containers!
    echo   Check Docker Desktop is running and try again.
    pause
    cd ..
    goto MAIN_MENU
)
timeout /t 3 /nobreak >nul

echo   Waiting for PostgreSQL to be ready...
echo   (This may take 10-15 seconds...)

REM Wait for PostgreSQL to be healthy
set POSTGRES_READY=0
for /L %%i in (1,1,15) do (
    timeout /t 2 /nobreak >nul
    docker exec wildlife-postgres pg_isready -U postgres >nul 2>&1
    if not errorlevel 1 (
        set POSTGRES_READY=1
        goto POSTGRES_READY
    )
)
:POSTGRES_READY

REM Check if containers are running
echo.
echo   Container status:
docker ps --filter "name=wildlife" --format "    {{.Names}}: {{.Status}}" 2>nul

if !POSTGRES_READY!==1 (
    echo   PostgreSQL: READY
) else (
    echo   WARNING: PostgreSQL may still be starting
    echo   Backend will retry connection on startup
)
echo   Docker services: Started
cd ..

REM Check Python venv
echo.
echo [3/6] Checking Python environment...
if not exist "wildlife-app\backend\venv\Scripts\python.exe" (
    echo   ERROR: Python virtual environment not found!
    echo   Expected: %CD%\wildlife-app\backend\venv\Scripts\python.exe
    pause
    goto MAIN_MENU
)
echo   Python venv: OK

REM Verify database is ready
echo.
echo [4/6] Verifying database connection...
cd wildlife-app\backend
echo import sys > test_db_ready.py
echo import time >> test_db_ready.py
echo from database import engine >> test_db_ready.py
echo max_attempts = 10 >> test_db_ready.py
echo for i in range(max_attempts): >> test_db_ready.py
echo     try: >> test_db_ready.py
echo         with engine.connect() as conn: >> test_db_ready.py
echo             pass >> test_db_ready.py
echo         print("  Database: READY") >> test_db_ready.py
echo         sys.exit(0) >> test_db_ready.py
echo     except Exception: >> test_db_ready.py
echo         if i ^< max_attempts - 1: >> test_db_ready.py
echo             time.sleep(2) >> test_db_ready.py
echo         else: >> test_db_ready.py
echo             print("  Database: NOT READY (PostgreSQL may still be starting)") >> test_db_ready.py
echo             print("  Backend will continue but database features may not work") >> test_db_ready.py
venv\Scripts\python.exe test_db_ready.py 2>nul
del test_db_ready.py >nul 2>&1
cd ..\..

REM Start SpeciesNet Server
echo.
echo [5/6] Starting SpeciesNet Server (port 8000)...
if not exist "wildlife-app\backend\speciesnet_server.py" (
    echo   ERROR: speciesnet_server.py not found!
    echo   Expected: %CD%\wildlife-app\backend\speciesnet_server.py
    pause
    goto MAIN_MENU
)
set "BACKEND_DIR=%CD%\wildlife-app\backend"
start "Wildlife SpeciesNet" cmd /k "title Wildlife SpeciesNet && cd /d "%BACKEND_DIR%" && echo ======================================== && echo   Wildlife SpeciesNet Server && echo   Port: 8000 && echo ======================================== && echo. && "%BACKEND_DIR%\venv\Scripts\python.exe" -m uvicorn speciesnet_server:app --host 0.0.0.0 --port 8000 --workers 4 && echo. && echo Press any key to close... && pause >nul"
timeout /t 3 /nobreak >nul

REM Start Backend
echo   Starting Backend Server (port 8001)...
if not exist "wildlife-app\backend\main.py" (
    echo   ERROR: main.py not found!
    echo   Expected: %CD%\wildlife-app\backend\main.py
    pause
    goto MAIN_MENU
)

REM Check if backend is already running
netstat -ano 2>nul | findstr ":8001" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo   WARNING: Port 8001 is already in use!
    echo   Stopping existing process...
    for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8001" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
    timeout /t 2 /nobreak >nul
)

start "Wildlife Backend" cmd /k "title Wildlife Backend && cd /d "%BACKEND_DIR%" && echo ======================================== && echo   Wildlife Backend Server && echo   Port: 8001 && echo ======================================== && echo. && "%BACKEND_DIR%\venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload && echo. && echo Press any key to close... && pause >nul"
timeout /t 5 /nobreak >nul

REM Wait for backend to be ready
echo   Waiting for Backend to start...
set BACKEND_READY=0
for /L %%i in (1,1,20) do (
    timeout /t 2 /nobreak >nul
    powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8001/health' -UseBasicParsing -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set BACKEND_READY=1
        echo   ✓ Backend is responding!
        goto BACKEND_READY
    )
    if %%i LEQ 5 (
        echo   Waiting... (attempt %%i/20)
    )
)
:BACKEND_READY

if !BACKEND_READY!==0 (
    echo   ⚠ Backend may still be starting (check the Backend window for errors)
)

REM Start Frontend
echo   Starting Frontend (port 3000)...
where npm >nul 2>&1
if errorlevel 1 (
    echo   ERROR: npm not found in PATH!
    pause
    goto MAIN_MENU
)
if not exist "wildlife-app\package.json" (
    echo   ERROR: package.json not found!
    echo   Expected: %CD%\wildlife-app\package.json
    pause
    goto MAIN_MENU
)
set "FRONTEND_DIR=%CD%\wildlife-app"
start "Wildlife Frontend" cmd /k "title Wildlife Frontend && cd /d "%FRONTEND_DIR%" && echo ======================================== && echo   Wildlife Frontend Server && echo   Port: 3000 && echo ======================================== && echo. && npm run dev && echo. && echo Press any key to close... && pause >nul"
timeout /t 3 /nobreak >nul

echo.
echo [6/6] Waiting for services to initialize...
echo   (This may take 10-15 seconds for first-time startup)
timeout /t 5 /nobreak >nul

REM Wait a bit more and check if services are starting
echo.
echo Checking if services are starting...
timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo   Services Started!
echo ========================================
echo.
echo Running health check...
echo   (Note: Services may need 10-15 more seconds to fully start)
echo.
call :HEALTH_CHECK_INTERNAL
echo.
echo If services show as NOT RUNNING, wait 10-15 seconds and run
echo health check again (option 5) or check the service windows for errors.
echo.
echo Press any key to return to menu...
pause >nul
goto MAIN_MENU

:STOP_SERVICES
cls
echo ========================================
echo   Stopping All Services
echo ========================================
echo.

REM Change to project root
cd /d "%~dp0.."

REM Stop Docker services
echo [1/4] Stopping Docker services...
if exist "wildlife-app\docker-compose.yml" (
    cd wildlife-app
    docker-compose down >nul 2>&1
    echo   Docker services: Stopped
    cd ..
) else (
    echo   docker-compose.yml not found, trying to stop containers by name...
    docker stop wildlife-postgres wildlife-motioneye >nul 2>&1
    docker rm wildlife-postgres wildlife-motioneye >nul 2>&1
)

echo.
echo [2/4] Stopping SpeciesNet Server...
taskkill /FI "WINDOWTITLE eq Wildlife SpeciesNet*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Wildlife SpeciesNet*" /T /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul
echo   SpeciesNet: Stopped

echo.
echo [3/4] Stopping Backend Server...
taskkill /FI "WINDOWTITLE eq Wildlife Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Wildlife Backend*" /T /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8001" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul
echo   Backend: Stopped

echo.
echo [4/4] Stopping Frontend...
taskkill /FI "WINDOWTITLE eq Wildlife Frontend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Wildlife Frontend*" /T /F >nul 2>&1
taskkill /IM node.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul
echo   Frontend: Stopped

echo.
echo ========================================
echo   All Services Stopped!
echo ========================================
echo.
pause
goto MAIN_MENU

:HEALTH_CHECK
cls
echo ========================================
echo   Service Health Check
echo ========================================
echo.
call :HEALTH_CHECK_INTERNAL
echo.
pause
goto MAIN_MENU

:HEALTH_CHECK_INTERNAL
echo Checking services...
echo.

REM Check Docker
echo Docker Services:
docker ps --filter "name=wildlife" --format "  {{.Names}}: {{.Status}}" 2>nul | findstr /V "^$" >nul
if errorlevel 1 (
    echo   Docker: Not accessible or no containers running
    docker ps 2>nul | findstr "wildlife" >nul
    if errorlevel 1 (
        echo   No wildlife containers found
    )
) else (
    docker ps --filter "name=wildlife" --format "  {{.Names}}: {{.Status}}" 2>nul
    echo   Docker: Running
)
echo.

REM Check SpeciesNet
echo SpeciesNet Server (port 8000):
tasklist /FI "WINDOWTITLE eq Wildlife SpeciesNet*" 2>nul | find /I "cmd.exe" >nul
if errorlevel 1 (
    echo   Process: NOT RUNNING
    echo   Action: Check if 'Wildlife SpeciesNet' window is open
) else (
    echo   Process: RUNNING
)
netstat -ano 2>nul | findstr ":8000" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo   Port 8000: Not listening
    echo   Action: Service may still be starting (wait 10-15 seconds)
) else (
    echo   Port 8000: Listening
)
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 10; $json = $r.Content | ConvertFrom-Json; if ($json.status -eq 'healthy' -or $json.model_loaded) { Write-Host '   Health: HEALTHY' -ForegroundColor Green } elseif ($json.status -eq 'loading') { Write-Host '   Health: LOADING MODEL (this can take 1-2 minutes)' -ForegroundColor Yellow } else { Write-Host '   Health: ERROR - Check service window' -ForegroundColor Red } } catch { Write-Host '   Health: NOT RESPONDING - Service may still be starting (model loading can take 1-2 minutes)' -ForegroundColor Yellow }" 2>nul
echo.

REM Check Backend
echo Backend Server (port 8001):
tasklist /FI "WINDOWTITLE eq Wildlife Backend*" 2>nul | find /I "cmd.exe" >nul
if errorlevel 1 (
    echo   Process: NOT RUNNING
    echo   Action: Check if 'Wildlife Backend' window is open
) else (
    echo   Process: RUNNING
)
netstat -ano 2>nul | findstr ":8001" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo   Port 8001: Not listening
    echo   Action: Service may still be starting (wait 10-15 seconds)
) else (
    echo   Port 8001: Listening
)
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8001/health' -UseBasicParsing -TimeoutSec 3; $json = $r.Content | ConvertFrom-Json; if ($json.status -eq 'healthy') { Write-Host '   Health: HEALTHY' -ForegroundColor Green } else { Write-Host '   Health: ERROR - Check service window' -ForegroundColor Red } } catch { Write-Host '   Health: NOT RESPONDING - Service may still be starting' -ForegroundColor Yellow }" 2>nul
echo.

REM Check Frontend
echo Frontend Server (port 3000):
tasklist /FI "WINDOWTITLE eq Wildlife Frontend*" 2>nul | find /I "cmd.exe" >nul
if errorlevel 1 (
    echo   Process: NOT RUNNING
    echo   Action: Check if 'Wildlife Frontend' window is open
    REM Check if port is in use by something else
    netstat -ano 2>nul | findstr ":3000" | findstr "LISTENING" >nul
    if not errorlevel 1 (
        echo   WARNING: Port 3000 is in use by another process!
        echo   Action: Stop other service using port 3000 or change frontend port
    )
) else (
    echo   Process: RUNNING
)
netstat -ano 2>nul | findstr ":3000" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo   Port 3000: Not listening
    echo   Action: Service may still be starting (wait 10-15 seconds)
) else (
    echo   Port 3000: Listening
)
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:3000' -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -eq 200) { Write-Host '   Health: HEALTHY' -ForegroundColor Green } else { Write-Host '   Health: ERROR - Check service window' -ForegroundColor Red } } catch { Write-Host '   Health: NOT RESPONDING - Service may still be starting' -ForegroundColor Yellow }" 2>nul
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
exit /b

:TROUBLESHOOT
cls
echo ========================================
echo   Troubleshooting / Diagnostics
echo ========================================
echo.

REM Change to project root
cd /d "%~dp0.."

echo Checking prerequisites...
echo.

REM Check Docker
echo [1] Docker:
docker --version >nul 2>&1
if errorlevel 1 (
    echo   Status: NOT INSTALLED or not in PATH
    echo   Action: Install Docker Desktop
) else (
    docker --version
    docker ps >nul 2>&1
    if errorlevel 1 (
        echo   Status: INSTALLED but not running
        echo   Action: Start Docker Desktop
    ) else (
        echo   Status: INSTALLED and RUNNING
    )
)
echo.

REM Check Python
echo [2] Python:
python --version >nul 2>&1
if errorlevel 1 (
    echo   Status: NOT FOUND in PATH
    echo   Action: Install Python 3.11+ and add to PATH
) else (
    python --version
    cd wildlife-app\backend
    if exist "venv\Scripts\python.exe" (
        echo   Virtual Environment: FOUND
        echo   Path: %CD%\venv\Scripts\python.exe
    ) else (
        echo   Virtual Environment: NOT FOUND
        echo   Action: Run: cd backend ^&^& python -m venv venv
    )
    cd ..\..
)
echo.

REM Check Node.js
echo [3] Node.js:
node --version >nul 2>&1
if errorlevel 1 (
    echo   Status: NOT FOUND in PATH
    echo   Action: Install Node.js and add to PATH
) else (
    node --version
    npm --version
)
echo.

REM Check project structure
echo [4] Project Structure:
cd wildlife-app
if exist "backend\main.py" (
    echo   backend\main.py: FOUND
) else (
    echo   backend\main.py: NOT FOUND
)
if exist "backend\speciesnet_server.py" (
    echo   backend\speciesnet_server.py: FOUND
) else (
    echo   backend\speciesnet_server.py: NOT FOUND
)
if exist "package.json" (
    echo   package.json: FOUND
) else (
    echo   package.json: NOT FOUND
)
if exist "docker-compose.yml" (
    echo   docker-compose.yml: FOUND
) else (
    echo   docker-compose.yml: NOT FOUND
)
cd ..
echo.

REM Check ports
echo [5] Port Status:
netstat -ano 2>nul | findstr ":8000" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo   Port 8000: IN USE
    echo   Action: Stop service using port 8000 or use control script to stop
) else (
    echo   Port 8000: AVAILABLE
)
netstat -ano 2>nul | findstr ":8001" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo   Port 8001: IN USE
    echo   Action: Stop service using port 8001 or use control script to stop
) else (
    echo   Port 8001: AVAILABLE
)
netstat -ano 2>nul | findstr ":3000" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo   Port 3000: IN USE
    echo   Action: Stop service using port 3000 or use control script to stop
) else (
    echo   Port 3000: AVAILABLE
)
echo.

echo ========================================
echo   Common Issues:
echo ========================================
echo.
echo If services show "NOT RUNNING" after starting:
echo   1. Wait 10-15 seconds and run health check again
echo   2. Check the service windows for error messages
echo   3. Verify all prerequisites are installed
echo   4. Make sure Docker Desktop is running
echo   5. Check that Python venv is created and activated
echo.
echo If ports show "IN USE":
echo   1. Run "Stop All Services" option
echo   2. Wait 5 seconds
echo   3. Try starting again
echo.
pause
goto MAIN_MENU

:QUICK_FIX
cls
echo ========================================
echo   Quick Backend Fix
echo ========================================
echo.
echo This will:
echo   1. Check/create Python virtual environment
echo   2. Install/update requirements
echo   3. Test backend imports
echo   4. Check database connection
echo.
pause

REM Change to project root
cd /d "%~dp0.."
cd wildlife-app\backend

echo.
echo [1] Checking Python venv...
if not exist "venv\Scripts\python.exe" (
    echo   Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo   ERROR: Failed to create venv!
        echo   Make sure Python is installed and in PATH
        pause
        goto MAIN_MENU
    )
    echo   Virtual environment created
) else (
    echo   Virtual environment: OK
)

echo.
echo [2] Installing/updating requirements...
venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo   WARNING: Some packages may have failed to install
)

echo.
echo [3] Testing backend imports...
echo import sys > test_import.py
echo try: >> test_import.py
echo     from main import app >> test_import.py
echo     print('   SUCCESS: Backend can be imported') >> test_import.py
echo except Exception as e: >> test_import.py
echo     print(f'   ERROR: {e}') >> test_import.py
echo     import traceback >> test_import.py
echo     traceback.print_exc() >> test_import.py
echo     sys.exit(1) >> test_import.py
venv\Scripts\python.exe test_import.py 2>&1
del test_import.py >nul 2>&1

if errorlevel 1 (
    echo.
    echo   Backend has import errors. Check the error above.
    pause
    goto MAIN_MENU
)

echo.
echo [4] Checking database connection...
echo import sys > test_db.py
echo try: >> test_db.py
echo     from database import engine >> test_db.py
echo     with engine.connect() as conn: >> test_db.py
echo         pass >> test_db.py
echo     print('   SUCCESS: Database connection OK') >> test_db.py
echo except Exception as e: >> test_db.py
echo     print(f'   WARNING: Database connection failed: {e}') >> test_db.py
echo     print('   Make sure Docker containers are running') >> test_db.py
venv\Scripts\python.exe test_db.py 2>&1
del test_db.py >nul 2>&1

echo.
echo ========================================
echo   Quick Fix Complete!
echo ========================================
echo.
echo Try starting the backend again (option 1)
echo.
pause
goto MAIN_MENU

:RESTART_ALL
cls
echo ========================================
echo   Complete Restart - All Services
echo ========================================
echo.
echo This will stop everything and restart cleanly.
echo.
pause

call "%~dp0restart-all.bat"

echo.
pause
goto MAIN_MENU

:CHECK_DOCKER
cls
echo ========================================
echo   Docker Status Check
echo ========================================
echo.
echo Running Docker diagnostics...
echo.

REM Change to project root
cd /d "%~dp0.."

call "%~dp0check-docker.bat"

echo.
pause
goto MAIN_MENU

:FORCE_START
cls
echo ========================================
echo   Force Start All Services
echo ========================================
echo.
echo This will start all services and wait for them to be ready.
echo.

REM Change to project root
cd /d "%~dp0.."

call "%~dp0force-start.bat"

echo.
pause
goto MAIN_MENU

:VERIFY_SYSTEM
cls
echo ========================================
echo   Complete System Verification
echo ========================================
echo.
echo Running comprehensive system check...
echo.

REM Change to project root
cd /d "%~dp0.."

call "%~dp0verify-system.bat"

echo.
pause
goto MAIN_MENU

:DIAGNOSE_BACKEND
cls
echo ========================================
echo   Backend Diagnostics
echo ========================================
echo.
echo Running comprehensive backend diagnostics...
echo.

REM Change to project root
cd /d "%~dp0.."
cd wildlife-app\backend

call "%~dp0diagnose-backend.bat"

echo.
pause
goto MAIN_MENU

:DIAGNOSE_SPECIESNET
cls
echo ========================================
echo   SpeciesNet Diagnostics
echo ========================================
echo.
echo Running SpeciesNet diagnostics...
echo.

REM Change to project root
cd /d "%~dp0.."
cd wildlife-app\backend

call "%~dp0diagnose-speciesnet.bat"

echo.
pause
goto MAIN_MENU

:EXIT
cls
echo.
echo Exiting Wildlife App Control...
echo.
timeout /t 1 /nobreak >nul
exit /b 0
