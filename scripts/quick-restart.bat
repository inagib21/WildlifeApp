@echo off
setlocal enabledelayedexpansion
title Wildlife App - Quick Restart

REM Change to project root
cd /d "%~dp0.."

echo ========================================
echo   Quick Restart - Stopping All Services
echo ========================================
echo.

REM Stop all processes on ports
echo Stopping services on ports 8000, 8001, 3000...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8001" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

REM Stop by window title
taskkill /F /FI "WINDOWTITLE eq Wildlife SpeciesNet*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Wildlife Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Wildlife Frontend*" >nul 2>&1

REM Stop Docker
if exist "wildlife-app\docker-compose.yml" (
    echo Stopping Docker containers...
    cd wildlife-app
    docker-compose down >nul 2>&1
    cd ..
)

echo [OK] All services stopped
timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo   Starting All Services
echo ========================================
echo.

REM Start everything
call scripts\start-all-fixed.bat

exit /b 0

