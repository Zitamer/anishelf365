# AniShelf365 - build Windows .exe via PyInstaller
# Run from project root:  powershell -ExecutionPolicy Bypass -File build.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== AniShelf365 build ===" -ForegroundColor Cyan
Write-Host ""

# 1. Sanity check
if (-not (Test-Path "main.py")) {
    Write-Host "main.py not found. Run from project root." -ForegroundColor Red
    exit 1
}

# 2. Check / install PyInstaller
Write-Host "Checking PyInstaller..." -ForegroundColor Yellow
$pyiVersion = $null
try {
    $pyiVersion = python -m PyInstaller --version 2>$null
} catch { }

if (-not $pyiVersion) {
    Write-Host "PyInstaller not installed. Installing..." -ForegroundColor Yellow
    python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install PyInstaller." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "PyInstaller $pyiVersion is installed." -ForegroundColor Green
}

# 3. Clean build/ and dist/
if (Test-Path "build") {
    Write-Host "Cleaning build/..." -ForegroundColor DarkGray
    Remove-Item -Recurse -Force "build"
}
if (Test-Path "dist") {
    Write-Host "Cleaning dist/..." -ForegroundColor DarkGray
    Remove-Item -Recurse -Force "dist"
}

# 4. Build
Write-Host ""
Write-Host "Building (this can take 1-3 minutes)..." -ForegroundColor Yellow
Write-Host ""
python -m PyInstaller --clean --noconfirm anishelf365.spec

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Build failed. See output above." -ForegroundColor Red
    exit 1
}

# 5. Result
Write-Host ""
$exe = "dist\AniShelf365\AniShelf365.exe"
if (Test-Path $exe) {
    $size = [math]::Round((Get-Item $exe).Length / 1MB, 2)
    $distSize = (Get-ChildItem "dist\AniShelf365" -Recurse -File |
                 Measure-Object Length -Sum).Sum / 1MB
    $distSize = [math]::Round($distSize, 1)

    Write-Host "=== Done ===" -ForegroundColor Green
    Write-Host "  exe:      $exe ($size MB)"
    Write-Host "  folder:   dist\AniShelf365\ ($distSize MB total)"
    Write-Host ""
    Write-Host "Check:" -ForegroundColor Cyan
    Write-Host "  1. Run $exe"
    Write-Host "  2. Complete onboarding (language, theme, folder, VLC, token)"
    Write-Host "  3. data\ folder must be created next to the exe"
    Write-Host "  4. Log: data\app.log"
} else {
    Write-Host "Something is wrong - exe not produced, though build finished." -ForegroundColor Red
    exit 1
}