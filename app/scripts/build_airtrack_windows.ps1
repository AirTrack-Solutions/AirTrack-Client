# AirTrack 1.0.0 'Wilbur' — Release 300
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

# Paths and Config
$certName = "AirTrack_Beta"
$pfxFolder = "C:\Users\trevo\docker\certs"
$pfxPath = "$pfxFolder\$certName.pfx"
$pfxPassword = "marianneanneroxannediane"
$issFile = "airtrack-windows.iss"
$outputExe = "AirTrack-Windows-Installer.exe"
$zipName = "AirTrack_full_0.9.0.zip"
$innosetupCompiler = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
$projectRoot = "C:\Users\trevo\docker\AirTrack-Windows-bak"
$timestamp = Get-Date -Format "HH:mm:ss"
$tempDir = "$env:TEMP\airtrack_package"

# Set working directory
Set-Location $projectRoot
Write-Host "[ $timestamp ] 📂 Working directory set to: $projectRoot"

# Ensure cert folder exists
if (-not (Test-Path $pfxFolder)) {
    Write-Host "[ $timestamp ] 📁 Cert folder not found. Creating: $pfxFolder"
    New-Item -ItemType Directory -Path $pfxFolder | Out-Null
}

# Check for PFX file
if (-not (Test-Path $pfxPath)) {
    Write-Host "[ $timestamp ] 🔐 PFX not found. Generating new self-signed certificate..."
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject "CN=AirTrack Beta Signing Cert" `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -KeyExportPolicy Exportable `
        -KeySpec Signature

    $securePwd = ConvertTo-SecureString -String $pfxPassword -AsPlainText -Force

    Export-PfxCertificate `
        -Cert $cert `
        -FilePath $pfxPath `
        -Password $securePwd

    Write-Host "[ $timestamp ] ✅ Certificate created and saved to $pfxPath"
} else {
    Write-Host "[ $timestamp ] 🔐 PFX certificate found."
}

# Clean old ZIP if it exists
if (Test-Path $zipName) {
    Write-Host "[ $timestamp ] 🗑️ Removing existing zip file: $zipName"
    Remove-Item $zipName -Force
}

# Prepare temp packaging folder
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -Path $tempDir -ItemType Directory | Out-Null

# Load .airtrackignore rules
$ignorePatterns = Get-Content ".airtrackignore" -ErrorAction SilentlyContinue |
    Where-Object { $_ -and -not ($_.Trim().StartsWith("#")) }

$shouldIgnore = {
    param($item)

    foreach ($pattern in $ignorePatterns) {
        $pattern = $pattern.Trim()
        if (-not $pattern) { continue }

        # Folder patterns (ends in slash)
        if ($pattern -like "*/" -or $pattern -like "*\\") {
            if ($item.PSIsContainer -and $item.FullName -like "*$($pattern.TrimEnd('/\'))*") {
                return $true
            }
            continue
        }

        # Wildcard match
        if ($item.Name -like $pattern) {
            return $true
        }

        # Exact filename match
        if ($item.Name -eq $pattern) {
            return $true
        }
    }
    return $false
}

Write-Host "[ $timestamp ] 📦 Staging files for ZIP (using .airtrackignore)..."

Get-ChildItem -Path "." -Recurse -Force |
    Where-Object {
        $_.FullName -notmatch '\\AppData\\' -and
        $_.FullName -notmatch '\\Temp\\' -and
        (-not (& $shouldIgnore $_) -or $_.Name -eq "AirTrack_images.tar")
    } |
    ForEach-Object {
        $relativePath = $_.FullName -replace [regex]::Escape($projectRoot), ""
        $destinationPath = Join-Path $tempDir $relativePath

        if ($_.PSIsContainer) {
            New-Item -ItemType Directory -Path $destinationPath -Force | Out-Null
        } else {
            New-Item -ItemType Directory -Path (Split-Path $destinationPath) -Force | Out-Null
            Copy-Item $_.FullName -Destination $destinationPath -Force
        }
    }

# Preview contents being zipped
Write-Host "`n🧪 Files staged for zipping:"
Get-ChildItem -Path $tempDir -Recurse | ForEach-Object { Write-Host "  - $($_.FullName)" }

# Compress temp folder contents
try {
    Compress-Archive -Path "$tempDir\*" -DestinationPath $zipName -Force -ErrorAction Stop
    Write-Host "[ $timestamp ] ✅ Full project ZIP created successfully."
} catch {
    Write-Host "[ $timestamp ] ❌ Compression failed: $($_.Exception.Message)"
    exit 1
}

# Clean temp
Remove-Item $tempDir -Recurse -Force

# Confirm Inno Setup exists
if (-not (Test-Path $innosetupCompiler)) {
    Write-Host "[ $timestamp ] ❌ Inno Setup not found at: $innosetupCompiler"
    exit 1
}

# Build the installer
Write-Host "[ $timestamp ] 🚀 Launching Inno Setup Compiler..."
& "$innosetupCompiler" $issFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ $timestamp ] ❌ Installer build failed with exit code $LASTEXITCODE."
    exit 1
}

Write-Host "[ $timestamp ] ✅ Installer built and signed successfully."
Write-Host "[ $timestamp ] 🎉 Build complete."

