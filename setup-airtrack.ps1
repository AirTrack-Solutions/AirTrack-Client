# AirTrack 1.0.0 "Wilbur" — Release 300
# Windows Git Installer
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

Write-Host ""
Write-Host "============================================"
Write-Host "   AirTrack 1.0.0 'Wilbur' — Windows Setup   "
Write-Host "============================================"
Write-Host ""

# --- REQUIRE ADMIN ---
If (-NOT ([Security.Principal.WindowsPrincipal]
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "This installer must be run as Administrator."
    Pause
    Exit
}

# --- CHECK GIT ---
If (!(Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Git is not installed. Please install Git first:"
    Write-Host "https://git-scm.com/download/win"
    Pause
    Exit
}

# --- CHECK DOCKER ---
If (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker Desktop is not installed."
    Write-Host "https://www.docker.com/products/docker-desktop/"
    Pause
    Exit
}

# --- INSTALL LOCATION ---
$installPath = "$env:USERPROFILE\AirTrack"
If (Test-Path $installPath) {
    Write-Host "Existing AirTrack folder found."
    $choice = Read-Host "Delete and reinstall? (Y/N)"
    If ($choice -ne "Y") {
        Write-Host "Install aborted."
        Exit
    }
    Remove-Item -Recurse -Force $installPath
}

# --- CLONE REPO ---
Write-Host "Cloning AirTrack repository..."
git clone https://github.com/Subhuti/AirTrack1.git $installPath
Set-Location $installPath

# --- ENV FILE ---
If (!(Test-Path ".env")) {
@"
FLASK_ENV=production
SECRET_KEY=CHANGE_ME
DATABASE_URL=mysql+pymysql://airtrack:airtrack@mariadb/airtrack
TZ=Australia/Sydney
"@ | Out-File -Encoding UTF8 ".env"
}

# --- DOCKER BUILD & START ---
Write-Host "Starting AirTrack..."
docker compose pull
docker compose build
docker compose up -d

# --- FIREWALL ---
Write-Host "Opening firewall port 5000..."
netsh advfirewall firewall add rule name="AirTrack" dir=in action=allow protocol=TCP localport=5000

# --- FINAL MESSAGE ---
Write-Host ""
Write-Host "============================================"
Write-Host " AirTrack is now running!"
Write-Host ""
Write-Host " Open in browser:"
Write-Host " http://localhost:5000"
Write-Host "============================================"
Write-Host ""
Pause

