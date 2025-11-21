@echo off
title Wildlife App Startup
echo ========================================
echo   Wildlife App Startup Script
echo ========================================
echo.

REM Change to wildlife-app directory
cd /d "%~dp0"
if not exist "wildlife-app" (
    echo ERROR: wildlife-app directory not found!
    pause
    exit /b 1
)

cd wildlife-app
echo Working directory: %CD%
echo.

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

REM Start Backend - using direct Python command
echo.
echo [3/4] Starting Backend (port 8001)...
echo Opening backend window...

REM Try to find Python
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH!
    echo Please install Python or add it to your PATH.
    pause
    exit /b 1
)

REM Start backend window with Python directly
start "Wildlife Backend" cmd /k "title Wildlife Backend && cd /d %CD%\backend && echo ======================================== && echo   Wildlife Backend Server && echo ======================================== && echo Directory: %CD%\backend && echo. && python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload && echo. && echo Backend stopped. && pause"

if errorlevel 1 (
    echo WARNING: Backend window may not have opened.
) else (
    echo Backend window opened.
)
timeout /t 3 /nobreak >nul

REM Start Frontend
echo.
echo [4/4] Starting Frontend (port 3000)...
echo Opening frontend window...

REM Check if npm exists
where npm >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm not found in PATH!
    echo Please install Node.js.
    pause
    exit /b 1
)

start "Wildlife Frontend" cmd /k "title Wildlife Frontend && cd /d %CD% && echo ======================================== && echo   Wildlife Frontend Server && echo ======================================== && echo Directory: %CD% && echo. && npm run dev && echo. && echo Frontend stopped. && pause"

if errorlevel 1 (
    echo WARNING: Frontend window may not have opened.
) else (
    echo Frontend window opened.
)
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   Startup Complete!
echo ========================================
echo.
echo Check your taskbar for these windows:
echo   - "Wildlife Backend" 
echo   - "Wildlife Frontend"
echo.
echo Services:
echo   - Backend:  http://localhost:8001
echo   - Frontend: http://localhost:3000
echo   - MotionEye: http://localhost:8765
echo.
pause

