@echo off
REM Quick test script for AI backends
REM Tests both images and videos if available

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ========================================
echo   AI Backend Test Suite
echo ========================================
echo.

REM Check if test_images folder exists
if not exist "test_images" (
    echo [WARN] test_images folder not found!
    echo.
    echo Would you like to download test images and videos?
    echo Run: download_media.bat
    echo.
    pause
    exit /b 1
)

REM Find first image
set IMAGE_FILE=
for %%f in (test_images\*.jpg test_images\*.jpeg test_images\*.png) do (
    if not defined IMAGE_FILE (
        set IMAGE_FILE=%%f
    )
)

REM Find first video
set VIDEO_FILE=
for %%f in (test_images\*.mp4 test_images\*.avi test_images\*.mov) do (
    if not defined VIDEO_FILE (
        set VIDEO_FILE=%%f
    )
)

echo Available test media:
if defined IMAGE_FILE (
    echo   [OK] Image: %IMAGE_FILE%
) else (
    echo   [WARN] No images found
)

if defined VIDEO_FILE (
    echo   [OK] Video: %VIDEO_FILE%
) else (
    echo   [WARN] No videos found
)

echo.
echo ========================================
echo   Testing Options
echo ========================================
echo.
echo [1] Test Images (all backends)
echo [2] Test Videos (all backends)
echo [3] Test Both
echo [4] Exit
echo.
set /p choice="Enter your choice (1-4): "

if "%choice%"=="1" goto TEST_IMAGES
if "%choice%"=="2" goto TEST_VIDEOS
if "%choice%"=="3" goto TEST_BOTH
if "%choice%"=="4" goto EXIT
goto EXIT

:TEST_IMAGES
if not defined IMAGE_FILE (
    echo [ERROR] No test images found!
    echo Run: download_media.bat
    pause
    exit /b 1
)
echo.
echo ========================================
echo   Testing Images
echo ========================================
echo.
python test_ai_backends.py "%IMAGE_FILE%"
pause
goto EXIT

:TEST_VIDEOS
if not defined VIDEO_FILE (
    echo [ERROR] No test videos found!
    echo Run: download_media.bat
    pause
    exit /b 1
)
echo.
echo ========================================
echo   Testing Videos
echo ========================================
echo.
python test_video_backends.py "%VIDEO_FILE%"
pause
goto EXIT

:TEST_BOTH
if not defined IMAGE_FILE (
    echo [ERROR] No test images found!
    pause
    exit /b 1
)
if not defined VIDEO_FILE (
    echo [ERROR] No test videos found!
    pause
    exit /b 1
)
echo.
echo ========================================
echo   Testing Images
echo ========================================
echo.
python test_ai_backends.py "%IMAGE_FILE%"
echo.
echo ========================================
echo   Testing Videos
echo ========================================
echo.
python test_video_backends.py "%VIDEO_FILE%"
pause
goto EXIT

:EXIT
exit /b 0

