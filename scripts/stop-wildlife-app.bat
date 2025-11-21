@echo off
echo ========================================
echo   Wildlife App Shutdown Script
echo ========================================
echo.

REM Change to project root (one level up from scripts folder)
cd /d "%~dp0.."
if not exist "wildlife-app" (
    echo Error: wildlife-app directory not found!
    echo Expected location: %CD%\wildlife-app
    pause
    exit /b 1
)
cd wildlife-app

echo Stopping Docker services...
docker-compose down

echo.
echo Stopping Node.js processes (Frontend)...
taskkill /F /IM node.exe /T 2>nul
if errorlevel 1 (
    echo No Node.js processes found.
) else (
    echo Node.js processes stopped.
)

echo.
echo Stopping Python processes (Backend)...
taskkill /F /IM python.exe /T 2>nul
if errorlevel 1 (
    echo No Python processes found.
) else (
    echo Python processes stopped.
)

echo.
echo ========================================
echo   All services stopped!
echo ========================================
echo.
pause

