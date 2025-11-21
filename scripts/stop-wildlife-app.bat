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
echo Stopping Backend processes...
REM First try to stop by window title (more specific)
taskkill /FI "WINDOWTITLE eq Wildlife Backend*" /F /T >nul 2>&1
timeout /t 1 /nobreak >nul
REM Then kill any remaining Python processes on port 8001
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8001" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
REM Fallback: kill all Python processes (be careful!)
taskkill /F /IM python.exe /T 2>nul
if errorlevel 1 (
    echo No Python processes found.
) else (
    echo Backend processes stopped.
)

echo.
echo ========================================
echo   All services stopped!
echo ========================================
echo.
pause

