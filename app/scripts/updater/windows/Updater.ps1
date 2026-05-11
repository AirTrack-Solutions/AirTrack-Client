# AirTrack 1.0.0 'Wilbur' — Release 300
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

# Windows updater: uses .zip + .zip.sha256, flips 'current' junction if possible and updates current.txt
$ErrorActionPreference = "Stop"

Function Read-Env($path) {
  $map = @{}
  Get-Content $path | ForEach-Object {
    $s = $_.Trim()
    if (-not $s -or $s.StartsWith("#")) { return }
    $i = $s.IndexOf("=")
    $k = $s.Substring(0,$i).Trim()
    $v = $s.Substring($i+1).Trim()
    $map[$k] = $v
  }
  return $map
}

$Here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $Here "..\common.env"
$E       = Read-Env $EnvFile

$InstallRoot = Join-Path $env:USERPROFILE $E["WINDOWS_INSTALL_REL"]
$ReleasesDir = Join-Path $InstallRoot $E["RELEASES_DIRNAME"]
$LogDir      = Join-Path $InstallRoot $E["LOG_DIRNAME"]
$CurrentName = $E["CURRENT_POINTER_NAME"]
$CurrentPath = Join-Path $InstallRoot $CurrentName
$CurrentTxt  = Join-Path $InstallRoot "current.txt"

$RemoteBase  = "https://raw.githubusercontent.com/$($E["GITHUB_OWNER"])/$($E["GITHUB_REPO"])/$($E["GITHUB_BRANCH"])"
$VersionUrl  = "$RemoteBase/VERSION"

New-Item -ItemType Directory -Force -Path $ReleasesDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$TS = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$LogFile = Join-Path $LogDir "updater_windows_$TS.log"
Start-Transcript -Path $LogFile -IncludeInvocationHeader | Out-Null

try {
  # Local version is from current.txt (preferred) or junction target name
  $LocalVersion = "0.0.0"
  if (Test-Path $CurrentTxt) {
    $LocalVersion = (Get-Content $CurrentTxt -ErrorAction SilentlyContinue).Trim()
    if ([string]::IsNullOrWhiteSpace($LocalVersion)) { $LocalVersion = "0.0.0" }
  }
  Write-Host "[*] Local version: $LocalVersion"

  Write-Host "[*] Fetching remote VERSION…"
  $RemoteVersion = (Invoke-WebRequest -UseBasicParsing -Uri $VersionUrl).Content.Trim()
  if ([string]::IsNullOrWhiteSpace($RemoteVersion)) { throw "Empty remote VERSION" }
  Write-Host "[*] Remote version: $RemoteVersion"

  function ToInt($ver) {
    $p = $ver.Split(".")
    return "{0:D3}{1:D3}{2:D3}" -f [int]$p[0], [int]$p[1], [int]$p[2]
  }

  if     ((ToInt $LocalVersion) -eq (ToInt $RemoteVersion)) { Write-Host "[=] Up to date."; return }
  elseif ((ToInt $LocalVersion) -gt (ToInt $RemoteVersion)) { Write-Host "[?] Local newer; skip."; return }

  $Zip     = "$($E["PKG_PREFIX"])-$RemoteVersion.zip"
  $ZipSha  = "$Zip.sha256"
  $Tmp     = New-Item -ItemType Directory -Force -Path ([IO.Path]::GetTempPath() + [GUID]::NewGuid()) | Select -ExpandProperty FullName
  $ZipPath = Join-Path $Tmp $Zip
  $ShaPath = Join-Path $Tmp $ZipSha

  Write-Host "[*] Downloading $Zip and $ZipSha…"
  Invoke-WebRequest -UseBasicParsing -Uri "$RemoteBase/releases/$Zip"    -OutFile $ZipPath
  Invoke-WebRequest -UseBasicParsing -Uri "$RemoteBase/releases/$ZipSha" -OutFile $ShaPath

  Write-Host "[*] Verifying checksum…"
  $expected = (Get-Content $ShaPath).Trim() -replace '\s+.*$',''
  $actual   = (Get-FileHash -Algorithm SHA256 -Path $ZipPath).Hash.ToLower()
  if ($actual.ToLower() -ne $expected.ToLower()) {
    throw "Checksum mismatch! expected=$expected actual=$actual"
  }

  $NewDir = Join-Path $ReleasesDir $RemoteVersion
  New-Item -ItemType Directory -Force -Path $NewDir | Out-Null
  Write-Host "[*] Extracting → $NewDir"
  Expand-Archive -Path $ZipPath -DestinationPath $NewDir -Force

  # Update pointer(s)
  Set-Content -Path $CurrentTxt -Value $RemoteVersion

  if (Test-Path $CurrentPath) {
    cmd /c "rmdir `"$CurrentPath`"" | Out-Null  # removes junction
  }
  # Try to create a directory junction 'current' → version dir (no admin needed on most systems)
  cmd /c "mklink /J `"$CurrentPath`" `"$NewDir`"" | Out-Null

  Write-Host "[✓] current → $NewDir"
}
finally {
  Stop-Transcript | Out-Null
}

