@echo off
cd /d "%~dp0..\wildlife-app\backend"
if not exist "venv\Scripts\python.exe" (
    echo ERROR: Python virtual environment not found!
    echo Expected: %CD%\venv\Scripts\python.exe
    pause
    exit /b 1
)
if not exist "main.py" (
    echo ERROR: main.py not found!
    pause
    exit /b 1
)
echo Starting Backend Server on port 8001...
start "Wildlife Backend" cmd /k "title Wildlife Backend && cd /d %CD% && echo ======================================== && echo   Wildlife Backend Server && echo   Port: 8001 && echo ======================================== && echo. && venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload && echo. && echo Press any key to close... && pause >nul"
timeout /t 3 /nobreak >nul
echo Backend starting in new window...
echo Waiting for backend to be ready...
set BACKEND_READY=0
for /L %%i in (1,1,15) do (
    timeout /t 2 /nobreak >nul
    powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8001/health' -UseBasicParsing -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set BACKEND_READY=1
        echo   Backend is responding!
        goto BACKEND_READY
    )
    if %%i LEQ 5 (
        echo   Waiting... (attempt %%i/15)
    )
)
:BACKEND_READY
if %BACKEND_READY%==0 (
    echo   WARNING: Backend may still be starting (check the Backend window for errors)
)
echo.
echo Backend startup complete!
pause

