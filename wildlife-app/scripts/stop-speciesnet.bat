@echo off
REM Stop SpeciesNet server on port 8000

echo ========================================
echo Stopping SpeciesNet Server (Port 8000)
echo ========================================
echo.

REM Find process using port 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    set PID=%%a
    echo Found process %PID% using port 8000
    taskkill /PID %%a /F
    echo Process %PID% terminated
)

REM Wait a moment
timeout /t 2 /nobreak >nul

REM Check if port is free
netstat -ano | findstr :8000
if %errorlevel% == 0 (
    echo WARNING: Port 8000 is still in use
) else (
    echo SUCCESS: Port 8000 is now free
)

pause

