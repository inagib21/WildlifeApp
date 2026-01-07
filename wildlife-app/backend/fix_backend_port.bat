@echo off
REM Fix backend port 8001 issue - kills any process using the port

echo ========================================
echo   Fixing Backend Port 8001
echo ========================================
echo.

echo Checking for processes on port 8001...
netstat -ano | findstr ":8001" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo   [OK] Port 8001 is free
    goto END
)

echo   [WARN] Port 8001 is in use
echo.
echo Killing processes on port 8001...

for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8001" ^| findstr "LISTENING"') do (
    echo   Killing process ID: %%a
    taskkill /F /PID %%a >nul 2>&1
    if errorlevel 1 (
        echo   [WARN] Could not kill process %%a (may require admin rights)
    ) else (
        echo   [OK] Process %%a killed
    )
)

timeout /t 2 /nobreak >nul

echo.
echo Verifying port is free...
netstat -ano | findstr ":8001" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo   [OK] Port 8001 is now free
    echo.
    echo You can now start the backend:
    echo   scripts\start-backend-only.bat
    echo   OR
    echo   scripts\control.bat (select option 1)
) else (
    echo   [FAIL] Port 8001 is still in use
    echo   Try running this script as Administrator
)

:END
echo.
pause

