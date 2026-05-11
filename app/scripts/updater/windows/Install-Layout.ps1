# AirTrack 1.0.0 'Wilbur' — Release 300
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

Param()
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $Here "..\common.env"
# Load KEY=VALUE env file
$envMap = @{}
Get-Content $EnvFile | ForEach-Object {
  $s = $_.Trim()
  if (-not $s -or $s.StartsWith("#")) { return }
  $i = $s.IndexOf("=")
  $k = $s.Substring(0,$i).Trim()
  $v = $s.Substring($i+1).Trim()
  $envMap[$k] = $v
}

$InstallRoot = Join-Path $env:USERPROFILE $envMap["WINDOWS_INSTALL_REL"]
$ReleasesDir = Join-Path $InstallRoot $envMap["RELEASES_DIRNAME"]
$LogDir      = Join-Path $InstallRoot $envMap["LOG_DIRNAME"]
$CurrentName = $envMap["CURRENT_POINTER_NAME"]
$CurrentPath = Join-Path $InstallRoot $CurrentName

New-Item -ItemType Directory -Force -Path $ReleasesDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# Maintain both a junction 'current' (if possible) and a 'current.txt' pointer (always works)
$CurrentTxt = Join-Path $InstallRoot "current.txt"
if (-not (Test-Path $CurrentTxt)) { Set-Content -Path $CurrentTxt -Value "" }

if (-not (Test-Path $CurrentPath)) {
  # Create a junction pointing to releases folder initially
  cmd /c "mklink /J `"$CurrentPath`" `"$ReleasesDir`"" | Out-Null
}

Write-Host "Windows layout ready:"
Write-Host "  $InstallRoot"
Write-Host "  $ReleasesDir"
Write-Host "  $CurrentPath  (junction if permissions allow)"
Write-Host "  $CurrentTxt   (text pointer)"
Write-Host "  $LogDir"

