@echo off
REM Start SpeciesNet server

echo ========================================
echo Starting SpeciesNet Server
echo ========================================
echo.

REM Check if port 8000 is in use
netstat -ano | findstr :8000 | findstr LISTENING >nul
if %errorlevel% == 0 (
    echo ERROR: Port 8000 is already in use!
    echo.
    echo Please stop the existing SpeciesNet server first:
    echo   scripts\stop-speciesnet.bat
    echo.
    pause
    exit /b 1
)

REM Navigate to backend directory
cd /d "%~dp0..\wildlife-app\backend"

REM Check if venv exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo WARNING: Virtual environment not found at venv\Scripts\activate.bat
    echo Continuing with system Python...
)

echo.
echo Starting SpeciesNet server on port 8000...
echo.

REM Start SpeciesNet server
python -m uvicorn speciesnet_server:app --host 0.0.0.0 --port 8000 --reload

pause

