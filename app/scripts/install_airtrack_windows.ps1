# AirTrack 1.0.0 'Wilbur'
# Copyright (c) 2025 Trevor ("Subhuti"). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC
#
# install_airtrack_windows.ps1
# Run automatically by the Inno Setup installer during [Run].
# Can also be run manually to repair or re-initialise AirTrack.
#
# Usage: powershell.exe -ExecutionPolicy Bypass -File install_airtrack_windows.ps1 [<path-to-zip>]

param(
    [string]$ZipPath = ""
)

$ErrorActionPreference = "Continue"
$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# ── Helpers ───────────────────────────────────────────────────────────────────

function Step($n, $msg) {
    Write-Host ""
    Write-Host "[$n/5] $msg"
}

function Wait-DockerReady {
    Write-Host "      Waiting for Docker daemon..."
    for ($i = 0; $i -lt 30; $i++) {
        docker info 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { return $true }
        Start-Sleep -Seconds 2
        Write-Host "      ." -NoNewline
    }
    Write-Host ""
    return $false
}

# ── Banner ────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "  ============================================"
Write-Host "   AirTrack 1.0.0 'Wilbur' — Windows Setup  "
Write-Host "  ============================================"

# ── Step 1: Check Docker Desktop ──────────────────────────────────────────────

Step 1 "Checking Docker Desktop..."

$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Host ""
    Write-Host "  ERROR: Docker Desktop is not installed."
    Write-Host ""
    Write-Host "  AirTrack requires Docker Desktop to run."
    Write-Host "  Download it from:"
    Write-Host "  https://www.docker.com/products/docker-desktop/"
    Write-Host ""
    Write-Host "  After installing Docker Desktop, run start_airtrack.bat"
    Write-Host "  to launch AirTrack."
    Write-Host ""
    Read-Host "  Press Enter to open the Docker Desktop download page"
    Start-Process "https://www.docker.com/products/docker-desktop/"
    exit 1
}

# Start Docker Desktop if daemon isn't running
docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "      Docker Desktop is installed but not running. Starting it..."
    $dockerExe = "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerExe) {
        Start-Process $dockerExe
    } else {
        Start-Process "Docker Desktop"
    }
    $ready = Wait-DockerReady
    if (-not $ready) {
        Write-Host ""
        Write-Host "  ERROR: Docker Desktop did not start in time."
        Write-Host "  Please start Docker Desktop manually, then run start_airtrack.bat"
        Write-Host ""
        Read-Host "  Press Enter to exit"
        exit 1
    }
}

Write-Host "      Docker Desktop is running."

# ── Step 2: Extract project files ─────────────────────────────────────────────

Step 2 "Extracting AirTrack files..."

if ($ZipPath -and (Test-Path $ZipPath)) {
    try {
        Expand-Archive -Path $ZipPath -DestinationPath $AppDir -Force
        Write-Host "      Project files extracted."
    } catch {
        Write-Host "      WARNING: Could not extract zip: $($_.Exception.Message)"
    }
} else {
    Write-Host "      No zip archive provided — skipping extraction."
}

# ── Step 3: Load Docker images ─────────────────────────────────────────────────

Step 3 "Loading Docker images (this may take a few minutes)..."

$tarFile = Join-Path $AppDir "AirTrack_images.tar"
if (Test-Path $tarFile) {
    Write-Host "      Loading from AirTrack_images.tar..."
    docker load -i $tarFile
    if ($LASTEXITCODE -ne 0) {
        Write-Host "      Image load reported an error — trying docker compose pull instead..."
        Set-Location $AppDir
        docker compose pull
    } else {
        Write-Host "      Images loaded successfully."
    }
} else {
    Write-Host "      Image archive not found — pulling from Docker Hub (internet required)..."
    Set-Location $AppDir
    docker compose pull
}

# ── Step 4: Create .env ─────────────────────────────────────────────────────────

Step 4 "Configuring environment..."

$envFile = Join-Path $AppDir ".env"
if (-not (Test-Path $envFile)) {
    # Generate a random 64-char secret key
    $secret = ([System.Guid]::NewGuid().ToString("N") + [System.Guid]::NewGuid().ToString("N")).ToUpper()

    # Best-guess local timezone
    $tz = try {
        $winTz = [System.TimeZoneInfo]::Local.Id
        # Map common Windows TZ IDs to IANA names
        $tzMap = @{
            "AUS Eastern Standard Time" = "Australia/Sydney"
            "E. Australia Standard Time" = "Australia/Brisbane"
            "Cen. Australia Standard Time" = "Australia/Adelaide"
            "W. Australia Standard Time" = "Australia/Perth"
            "Eastern Standard Time" = "America/New_York"
            "Central Standard Time" = "America/Chicago"
            "Mountain Standard Time" = "America/Denver"
            "Pacific Standard Time" = "America/Los_Angeles"
            "GMT Standard Time" = "Europe/London"
            "UTC" = "UTC"
        }
        if ($tzMap.ContainsKey($winTz)) { $tzMap[$winTz] } else { "UTC" }
    } catch { "UTC" }

    @"
FLASK_ENV=production
SECRET_KEY=$secret
DB_HOST=airtrack-db
DB_USER=airtrack
DB_PASSWORD=airtrack
DB_NAME=airtrack
TZ=$tz
"@ | Out-File -Encoding UTF8 -NoNewline $envFile
    Write-Host "      Created .env (timezone: $tz)"
} else {
    Write-Host "      Existing .env kept."
}

# ── Step 5: Start AirTrack ──────────────────────────────────────────────────────

Step 5 "Starting AirTrack..."

Set-Location $AppDir
docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  ERROR: docker compose up failed."
    Write-Host "  Make sure Docker Desktop is running and try start_airtrack.bat"
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit 1
}

# Open firewall port (silent — may require admin; non-fatal if it fails)
try {
    netsh advfirewall firewall add rule name="AirTrack" dir=in action=allow protocol=TCP localport=5000 2>&1 | Out-Null
} catch {}

# Give containers a moment to initialise before opening the browser
Write-Host "      Containers started. Opening browser in 5 seconds..."
Start-Sleep -Seconds 5
Start-Process "http://localhost:5000"

Write-Host ""
Write-Host "  ============================================"
Write-Host "   AirTrack is running!"
Write-Host "   Open your browser to: http://localhost:5000"
Write-Host ""
Write-Host "   To launch AirTrack in future:"
Write-Host "   Double-click start_airtrack.bat"
Write-Host "  ============================================"
Write-Host ""
