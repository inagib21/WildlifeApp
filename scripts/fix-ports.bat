@echo off
setlocal enabledelayedexpansion
title Wildlife App - Fix Port Conflicts

echo ========================================
echo   Fixing Port Conflicts
echo ========================================
echo.
echo   Stopping all processes on ports 8000, 8001, 3000...
echo.

REM Stop processes on ports
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo   Stopped process %%a on port 8000
)

for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8001" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo   Stopped process %%a on port 8001
)

for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo   Stopped process %%a on port 3000
)

REM Stop by window title
taskkill /F /FI "WINDOWTITLE eq Wildlife SpeciesNet*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Wildlife Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Wildlife Frontend*" >nul 2>&1

echo.
echo   [OK] All ports cleared
echo.
echo   Waiting 2 seconds...
timeout /t 2 /nobreak >nul

echo.
echo   Port status:
netstat -ano 2>nul | findstr ":8000 :8001 :3000" | findstr "LISTENING"
if errorlevel 1 (
    echo   [OK] All ports are now free
) else (
    echo   [WARN] Some ports may still be in use
)

echo.
pause

