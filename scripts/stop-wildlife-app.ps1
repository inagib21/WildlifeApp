# Wildlife App Shutdown Script (PowerShell)
# Double-click this file or run: powershell -ExecutionPolicy Bypass -File stop-wildlife-app.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Wildlife App Shutdown Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory and go up one level to project root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$wildlifeAppDir = Join-Path $projectRoot "wildlife-app"

if (-not (Test-Path $wildlifeAppDir)) {
    Write-Host "Error: wildlife-app directory not found!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Change to wildlife-app directory
Set-Location $wildlifeAppDir

# Stop Docker services
Write-Host "Stopping Docker services..." -ForegroundColor Yellow
try {
    docker-compose down
    Write-Host "Docker services stopped." -ForegroundColor Green
} catch {
    Write-Host "Error stopping Docker services." -ForegroundColor Red
}

Write-Host ""
Write-Host "Stopping Node.js processes (Frontend)..." -ForegroundColor Yellow
$nodeProcesses = Get-Process -Name "node" -ErrorAction SilentlyContinue
if ($nodeProcesses) {
    Stop-Process -Name "node" -Force -ErrorAction SilentlyContinue
    Write-Host "Node.js processes stopped." -ForegroundColor Green
} else {
    Write-Host "No Node.js processes found." -ForegroundColor Gray
}

Write-Host ""
Write-Host "Stopping Python processes (Backend)..." -ForegroundColor Yellow
$pythonProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
    Write-Host "Python processes stopped." -ForegroundColor Green
} else {
    Write-Host "No Python processes found." -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All services stopped!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"

