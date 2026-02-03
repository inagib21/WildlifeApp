@echo off
title Wildlife Backend Server - Debug Mode
cd /d "%~dp0"
echo ========================================
echo Wildlife Backend Server - Debug Mode
echo ========================================
echo.

echo [1] Checking Python...
python --version
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    pause
    exit /b 1
)
echo.

echo [2] Checking for virtual environment...
if exist "venv\Scripts\python.exe" (
    echo Found virtual environment, using venv Python...
    set PYTHON_CMD=venv\Scripts\python.exe
) else (
    echo No virtual environment found, using system Python...
    set PYTHON_CMD=python
)
echo.

echo [3] Checking dependencies...
%PYTHON_CMD% -c "import fastapi; print('FastAPI: OK')" 2>nul || echo FastAPI: MISSING
%PYTHON_CMD% -c "import uvicorn; print('Uvicorn: OK')" 2>nul || echo Uvicorn: MISSING
%PYTHON_CMD% -c "import sqlalchemy; print('SQLAlchemy: OK')" 2>nul || echo SQLAlchemy: MISSING
echo.

echo [4] Starting backend server...
echo ========================================
echo.
%PYTHON_CMD% start_backend.py
echo.
echo ========================================
echo Backend server stopped.
echo.
pause
