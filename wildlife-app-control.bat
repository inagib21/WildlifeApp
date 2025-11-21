@echo off
setlocal enabledelayedexpansion
title Wildlife App Control Center

:MAIN_MENU
cls
echo ========================================
echo   Wildlife App Control Center
echo ========================================
echo.
echo [1] Start All Services
echo [2] Stop All Services
echo [3] Check Service Status
echo [4] Exit
echo.
set /p choice="Enter your choice (1-4): "

if "%choice%"=="1" goto START_SERVICES
if "%choice%"=="2" goto STOP_SERVICES
if "%choice%"=="3" goto CHECK_STATUS
if "%choice%"=="4" goto EXIT
goto MAIN_MENU

:START_SERVICES
cls
echo ========================================
echo   Starting All Services
echo ========================================
echo.

REM Change to wildlife-app directory
cd /d "%~dp0"
if not exist "wildlife-app" (
    echo ERROR: wildlife-app directory not found!
    pause
    goto MAIN_MENU
)

cd wildlife-app
echo Working directory: %CD%
echo.

REM Check if services are already running
tasklist /FI "WINDOWTITLE eq Wildlife Backend*" 2>nul | find /I "cmd.exe" >nul
if not errorlevel 1 (
    echo WARNING: Backend appears to be already running!
    set /p continue="Continue anyway? (y/n): "
    if /i not "!continue!"=="y" goto MAIN_MENU
)

tasklist /FI "WINDOWTITLE eq Wildlife Frontend*" 2>nul | find /I "cmd.exe" >nul
if not errorlevel 1 (
    echo WARNING: Frontend appears to be already running!
    set /p continue="Continue anyway? (y/n): "
    if /i not "!continue!"=="y" goto MAIN_MENU
)

REM Check if Docker is running
echo [1/4] Checking Docker...
docker ps >nul 2>&1
if errorlevel 1 (
    echo Docker not running, but continuing...
) else (
    echo Docker is running.
)

REM Start Docker services
echo.
echo [2/4] Starting Docker services...
docker-compose up -d 2>nul
echo Docker services check complete.
timeout /t 2 /nobreak >nul

REM Start Backend
echo.
echo [3/4] Starting Backend (port 8001)...
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH!
    pause
    goto MAIN_MENU
)

start "Wildlife Backend" cmd /k "title Wildlife Backend && cd /d %CD%\backend && echo ======================================== && echo   Wildlife Backend Server && echo ======================================== && echo Directory: %CD%\backend && echo. && python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload && echo. && echo Backend stopped. && pause"
timeout /t 2 /nobreak >nul
echo Backend window opened.

REM Start Frontend
echo.
echo [4/4] Starting Frontend (port 3000)...
where npm >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm not found in PATH!
    pause
    goto MAIN_MENU
)

start "Wildlife Frontend" cmd /k "title Wildlife Frontend && cd /d %CD% && echo ======================================== && echo   Wildlife Frontend Server && echo ======================================== && echo Directory: %CD% && echo. && npm run dev && echo. && echo Frontend stopped. && pause"
timeout /t 2 /nobreak >nul
echo Frontend window opened.

echo.
echo ========================================
echo   All Services Started!
echo ========================================
echo.
echo Services are running:
echo   - Backend:  http://localhost:8001
echo   - Frontend: http://localhost:3000
echo   - MotionEye: http://localhost:8765
echo.
echo Windows opened:
echo   - "Wildlife Backend" 
echo   - "Wildlife Frontend"
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

REM Stop Docker services
echo [1/3] Stopping Docker services...
cd /d "%~dp0wildlife-app"
if exist "docker-compose.yml" (
    docker-compose down 2>nul
    echo Docker services stopped.
) else (
    echo Docker compose file not found, skipping...
)

REM Stop Backend
echo.
echo [2/3] Stopping Backend...
taskkill /FI "WINDOWTITLE eq Wildlife Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Wildlife Backend*" /T /F >nul 2>&1
timeout /t 1 /nobreak >nul
echo Backend stopped.

REM Stop Frontend
echo.
echo [3/3] Stopping Frontend...
taskkill /FI "WINDOWTITLE eq Wildlife Frontend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Wildlife Frontend*" /T /F >nul 2>&1
timeout /t 1 /nobreak >nul
echo Frontend stopped.

REM Also kill any remaining Node.js processes (in case frontend didn't close cleanly)
taskkill /IM node.exe /F >nul 2>&1

echo.
echo ========================================
echo   All Services Stopped!
echo ========================================
echo.
pause
goto MAIN_MENU

:CHECK_STATUS
cls
echo ========================================
echo   Service Status
echo ========================================
echo.

REM Check Docker
echo Docker Services:
docker ps --filter "name=wildlife" --format "table {{.Names}}\t{{.Status}}" 2>nul
if errorlevel 1 (
    echo   Docker: Not accessible or not running
) else (
    echo   Docker: Running
)
echo.

REM Check Backend
echo Backend (port 8001):
tasklist /FI "WINDOWTITLE eq Wildlife Backend*" 2>nul | find /I "cmd.exe" >nul
if errorlevel 1 (
    echo   Status: NOT RUNNING
) else (
    echo   Status: RUNNING
    netstat -ano | findstr ":8001" | findstr "LISTENING" >nul
    if errorlevel 1 (
        echo   Port 8001: Not listening
    ) else (
        echo   Port 8001: Listening
    )
)
echo.

REM Check Frontend
echo Frontend (port 3000):
tasklist /FI "WINDOWTITLE eq Wildlife Frontend*" 2>nul | find /I "cmd.exe" >nul
if errorlevel 1 (
    echo   Status: NOT RUNNING
) else (
    echo   Status: RUNNING
    netstat -ano | findstr ":3000" | findstr "LISTENING" >nul
    if errorlevel 1 (
        echo   Port 3000: Not listening
    ) else (
        echo   Port 3000: Listening
    )
)
echo.

echo Access URLs:
echo   - Backend:  http://localhost:8001
echo   - Frontend: http://localhost:3000
echo   - MotionEye: http://localhost:8765
echo.
pause
goto MAIN_MENU

:EXIT
cls
echo.
echo Exiting Wildlife App Control Center...
echo.
timeout /t 1 /nobreak >nul
exit /b 0

