@echo off
title Wildlife App Startup
echo ========================================
echo   Wildlife App Startup Script (Simple)
echo ========================================
echo.

cd /d "%~dp0wildlife-app"
if errorlevel 1 (
    echo ERROR: Cannot find wildlife-app directory!
    pause
    exit /b 1
)

echo Current directory: %CD%
echo.

REM Start Backend in a new window
echo [1/2] Starting Backend...
echo Opening backend window at: %CD%
start "Wildlife Backend" cmd /k "title Wildlife Backend && cd /d %CD% && echo Starting Backend from: %CD% && echo. && npm run backend"
if errorlevel 1 (
    echo ERROR: Failed to open backend window!
) else (
    echo Backend window command sent.
)
timeout /t 3 /nobreak >nul

REM Start Frontend in a new window  
echo [2/2] Starting Frontend...
echo Opening frontend window at: %CD%
start "Wildlife Frontend" cmd /k "title Wildlife Frontend && cd /d %CD% && echo Starting Frontend from: %CD% && echo. && npm run dev"
if errorlevel 1 (
    echo ERROR: Failed to open frontend window!
) else (
    echo Frontend window command sent.
)
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   Windows should have opened!
echo ========================================
echo.
echo Check your taskbar for:
echo   - "Wildlife Backend" window
echo   - "Wildlife Frontend" window
echo.
pause

