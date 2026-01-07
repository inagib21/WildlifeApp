@echo off
REM Quick script to download test images and videos using Pexels API
REM Usage: download_media.bat [images_count] [videos_count]

setlocal enabledelayedexpansion

REM Your Pexels API key
set PEXELS_KEY=PZIghIm0CCKcLD0JMRdvMCyVflYiLqcBkRuPEzLorAp5WjWeofQEPekk

REM Default counts
set IMAGES=15
set VIDEOS=5

REM Override with command line arguments
if not "%1"=="" set IMAGES=%1
if not "%2"=="" set VIDEOS=%2

echo ========================================
echo   Downloading Test Media
echo ========================================
echo.
echo Images: %IMAGES%
echo Videos: %VIDEOS%
echo.

cd /d "%~dp0"

python download_test_images.py --count %IMAGES% --videos %VIDEOS% --pexels-key %PEXELS_KEY%

echo.
echo ========================================
echo   Download Complete!
echo ========================================
echo.
pause

