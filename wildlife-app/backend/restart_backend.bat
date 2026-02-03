@echo off
echo ============================================================
echo Restarting Backend Server
echo ============================================================
echo.

echo [1] Stopping existing backend processes...
taskkill /F /FI "WINDOWTITLE eq Wildlife Backend*" 2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq Wildlife Backend*" 2>nul
timeout /t 2 /nobreak >nul

echo [2] Clearing cache...
cd /d "%~dp0"
python restart_and_clear_cache.py

echo.
echo [3] Starting backend...
cd wildlife-app\backend
if exist venv\Scripts\python.exe (
    start "Wildlife Backend" venv\Scripts\python.exe start_backend.py
) else (
    start "Wildlife Backend" python start_backend.py
)

echo.
echo Backend restart initiated!
echo Check the new window for status.
echo.
pause
