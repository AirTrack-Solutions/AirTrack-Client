; Gate 3 proof of concept — Inno Setup orchestration
; Proves: single EXE installs MariaDB + AirTrack service with no user interaction beyond one click.
;
; BUILD PREREQUISITES (Trevor's laptop):
;   1. Run build.bat in this folder to produce dist\AirTrack\
;   2. Place mariadb-11.4-winx64.msi in this folder (rename from downloaded filename)
;   3. Install Inno Setup 6.x from jrsoftware.org
;   4. Open this file in Inno Setup, click Build > Compile
;   Output: Output\AirTrackGate3Setup.exe
;
; TEST (Marianne's PC — admin rights required, nothing else installed):
;   Run AirTrackGate3Setup.exe
;   When complete, browser opens http://localhost:5000
;   Expected: AirTrack OK — DB connected
;   Reboot, then verify localhost:5000 responds without any manual commands.

[Setup]
AppName=AirTrack Gate 3
AppVersion=0.0.3
DefaultDirName=C:\AirTrackTest
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputBaseFilename=AirTrackGate3Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
CreateUninstallRegKey=no
Uninstallable=no

[Files]
; MariaDB MSI — rename your download to mariadb-11.4-winx64.msi
Source: "mariadb-11.4-winx64.msi"; DestDir: "{tmp}"; Flags: deleteafterinstall

; Database helpers
Source: "init_db.sql"; DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "init_db.bat"; DestDir: "{tmp}"; Flags: deleteafterinstall

; MariaDB readiness check (PowerShell — no Python required on target)
Source: "wait_for_db.ps1"; DestDir: "{tmp}"; Flags: deleteafterinstall

; AirTrack bundle (built by build.bat)
Source: "dist\AirTrack\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Run]
; Step 1 — Install MariaDB silently on port 3307
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\mariadb-11.4-winx64.msi"" /quiet /norestart SERVICENAME=AirTrackDB PORT=3307 PASSWORD=Gate1RootPass! ALLOWREMOTEMACHINE=0 BUFFERPOOLSIZE=64 DATADIR=C:\AirTrackData\"; StatusMsg: "Installing MariaDB..."; Flags: waituntilterminated

; Step 2 — Wait for MariaDB to accept connections (TCP check, 30 x 2s attempts)
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NonInteractive -File ""{tmp}\wait_for_db.ps1"""; StatusMsg: "Waiting for database..."; Flags: waituntilterminated

; Step 3 — Create database and application user
Filename: "{tmp}\init_db.bat"; StatusMsg: "Initialising database..."; Flags: waituntilterminated

; Step 4 — Install AirTrack service (registers as Automatic / Delayed)
Filename: "{app}\AirTrack.exe"; Parameters: "install"; StatusMsg: "Installing AirTrack service..."; Flags: waituntilterminated

; Step 5 — Set service dependency: AirTrackGate3 waits for AirTrackDB on every boot
Filename: "sc.exe"; Parameters: "config AirTrackGate3 depend= AirTrackDB"; StatusMsg: "Configuring service dependency..."; Flags: waituntilterminated

; Step 6 — Start AirTrack
Filename: "{app}\AirTrack.exe"; Parameters: "start"; StatusMsg: "Starting AirTrack..."; Flags: waituntilterminated

; Step 7 — Open browser (post-install, skipped in silent mode)
Filename: "http://localhost:5000"; Flags: shellexec nowait postinstall skipifsilent; Description: "Open AirTrack in browser"
