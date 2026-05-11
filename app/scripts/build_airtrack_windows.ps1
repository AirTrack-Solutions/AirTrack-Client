# AirTrack 1.0.0 'Wilbur'
# Copyright (c) 2025 Trevor ("Subhuti"). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC
#
# build_airtrack_windows.ps1
# Builds the AirTrack Windows installer (.exe) using Inno Setup.
#
# Run from anywhere — this script auto-locates the project root
# (two directories above app/scripts/ where the script lives).
#
# PFX certificate password:
#   Put the password in   <script_dir>\.pfxpass   (one line, no quotes).
#   That file is git-ignored. If missing, you will be prompted.
#
# Optional parameters:
#   -ProjectRoot  Override the auto-detected project root directory.
#   -Version      Override the version (default: reads VERSION file).

#Requires -Version 5.1
param(
    [string]$ProjectRoot = "",
    [string]$Version     = ""
)

$ErrorActionPreference = "Stop"

# ── Resolve paths ─────────────────────────────────────────────────────────────

$ScriptDir = $PSScriptRoot

# Project root is two levels up from app/scripts/
if ($ProjectRoot -eq "") {
    $ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..\..\")).Path
}

# Version from VERSION file or parameter
if ($Version -eq "") {
    $versionFile = Join-Path $ProjectRoot "VERSION"
    $Version = if (Test-Path $versionFile) {
        (Get-Content $versionFile -Raw).Trim()
    } else { "1.0.0" }
}

$certName     = "AirTrack_Signing"
$pfxFolder    = Join-Path $env:USERPROFILE "docker\certs"
$pfxPath      = Join-Path $pfxFolder "$certName.pfx"
$pfxPassFile  = Join-Path $ScriptDir ".pfxpass"
$issFile      = Join-Path $ScriptDir "airtrack-windows.iss"
$zipName      = "AirTrack_full_$Version.zip"
$zipPath      = Join-Path $ScriptDir $zipName
$outputExe    = Join-Path $ScriptDir "AirTrack-Windows-Installer.exe"
$innoCompiler = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
$signtool     = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"
$tempDir      = Join-Path $env:TEMP "airtrack_build_$(Get-Random)"

function TS { Get-Date -Format "HH:mm:ss" }

Write-Host ""
Write-Host "[ $(TS) ] AirTrack Windows Build v$Version"
Write-Host "[ $(TS) ] Project root : $ProjectRoot"
Write-Host "[ $(TS) ] Script dir   : $ScriptDir"
Write-Host ""

# ── PFX password ───────────────────────────────────────────────────────────────

if (Test-Path $pfxPassFile) {
    $pfxPassword = (Get-Content $pfxPassFile -Raw).Trim()
    Write-Host "[ $(TS) ] PFX password  : loaded from .pfxpass"
} else {
    Write-Host "[ $(TS) ] .pfxpass not found — please enter the certificate password."
    $secPwd = Read-Host "  Certificate password" -AsSecureString
    $pfxPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secPwd)
    )
    Write-Host "[ $(TS) ] PFX password  : entered interactively"
}

# ── Certificate ────────────────────────────────────────────────────────────────

if (-not (Test-Path $pfxFolder)) {
    New-Item -ItemType Directory -Path $pfxFolder | Out-Null
    Write-Host "[ $(TS) ] Created cert folder: $pfxFolder"
}

if (-not (Test-Path $pfxPath)) {
    Write-Host "[ $(TS) ] No PFX found — generating self-signed code-signing certificate..."
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject "CN=AirTrack Signing Cert" `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -KeyExportPolicy Exportable `
        -KeySpec Signature
    $securePwd = ConvertTo-SecureString -String $pfxPassword -AsPlainText -Force
    Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $securePwd | Out-Null
    Write-Host "[ $(TS) ] Self-signed certificate saved: $pfxPath"
} else {
    Write-Host "[ $(TS) ] Certificate   : $pfxPath"
}

# ── Load .airtrackignore ────────────────────────────────────────────────────────

$ignoreFile = Join-Path $ProjectRoot ".airtrackignore"
$ignorePatterns = if (Test-Path $ignoreFile) {
    Get-Content $ignoreFile | Where-Object { $_ -and -not ($_.Trim().StartsWith("#")) }
} else { @() }

$shouldIgnore = {
    param($item)
    foreach ($pat in $ignorePatterns) {
        $pat = $pat.Trim()
        if (-not $pat) { continue }
        if ($pat -like "*/" -or $pat -like "*\\") {
            if ($item.PSIsContainer -and $item.FullName -like "*$($pat.TrimEnd('/\'))*") { return $true }
            continue
        }
        if ($item.Name -like $pat -or $item.Name -eq $pat) { return $true }
    }
    return $false
}

# ── Stage project files ────────────────────────────────────────────────────────

Write-Host "[ $(TS) ] Staging files for ZIP..."

if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
New-Item -Path $tempDir -ItemType Directory | Out-Null

Get-ChildItem -Path $ProjectRoot -Recurse -Force |
    Where-Object {
        $_.FullName -notmatch [regex]::Escape($tempDir) -and
        $_.FullName -notmatch '\\AppData\\' -and
        $_.FullName -notmatch '\\Temp\\' -and
        (-not (& $shouldIgnore $_))
    } |
    ForEach-Object {
        $rel = $_.FullName -replace [regex]::Escape($ProjectRoot), ""
        $dst = Join-Path $tempDir $rel
        if ($_.PSIsContainer) {
            New-Item -ItemType Directory -Path $dst -Force | Out-Null
        } else {
            New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null
            Copy-Item $_.FullName -Destination $dst -Force
        }
    }

# ── Compress ──────────────────────────────────────────────────────────────────

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

try {
    Write-Host "[ $(TS) ] Compressing to $zipName..."
    Compress-Archive -Path "$tempDir\*" -DestinationPath $zipPath -Force -ErrorAction Stop
    $sizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
    Write-Host "[ $(TS) ] ZIP created  : $zipName ($sizeMB MB)"
} catch {
    Write-Host "[ $(TS) ] ERROR: Compression failed: $($_.Exception.Message)"
    exit 1
} finally {
    Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}

# ── Build installer ────────────────────────────────────────────────────────────

if (-not (Test-Path $innoCompiler)) {
    Write-Host "[ $(TS) ] ERROR: Inno Setup 6 not found at: $innoCompiler"
    Write-Host "         Download from https://jrsoftware.org/isinfo.php"
    exit 1
}

Write-Host "[ $(TS) ] Running Inno Setup..."
& $innoCompiler $issFile /DAppVersion=$Version /DZipName=$zipName

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ $(TS) ] ERROR: Inno Setup failed (exit code $LASTEXITCODE)"
    exit 1
}

Write-Host "[ $(TS) ] Installer built: AirTrack-Windows-Installer.exe"

# ── Code-sign the installer ────────────────────────────────────────────────────

if (Test-Path $signtool) {
    Write-Host "[ $(TS) ] Signing installer..."
    & $signtool sign `
        /f $pfxPath `
        /p $pfxPassword `
        /fd sha256 `
        /tr http://timestamp.digicert.com `
        /td sha256 `
        $outputExe
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ $(TS) ] WARNING: Code signing failed (exit $LASTEXITCODE) — installer still usable."
    } else {
        Write-Host "[ $(TS) ] Installer signed successfully."
    }
} else {
    Write-Host "[ $(TS) ] signtool.exe not found — skipping code signing."
    Write-Host "         Install Windows SDK to enable signing."
}

Write-Host ""
Write-Host "[ $(TS) ] Build complete!"
Write-Host "[ $(TS) ] Output: $outputExe"
Write-Host ""
