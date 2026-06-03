; AirTrack Windows Installer
; Gate 3 — real app wired into proven installer skeleton
;
; BUILD (Trevor's laptop):
;   1. Run gates\gate3\build.bat from the AirTrack-Client repo root
;   2. Place mariadb-11.4-winx64.msi in gates\gate3\
;   3. Open this file in Inno Setup 6, Build > Compile
;   Output: gates\gate3\Output\AirTrackSetup.exe
;
; TEST (Marianne's PC — admin, nothing else required):
;   Run AirTrackSetup.exe
;   Browser should open to http://localhost:5000 showing the AirTrack UI
;   Reboot — browser should show the same without manual intervention

[Setup]
AppName=AirTrack
AppVersion=1.0.0
DefaultDirName=C:\AirTrack
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputBaseFilename=AirTrackSetup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
CreateUninstallRegKey=no
Uninstallable=no

[Files]
; MariaDB MSI — rename your download to mariadb-11.4-winx64.msi
Source: "mariadb-11.4-winx64.msi"; DestDir: "{tmp}"; Flags: deleteafterinstall

; Database init helpers
Source: "init_db.sql";  DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "schema.sql";   DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "init_db.bat";  DestDir: "{tmp}"; Flags: deleteafterinstall

; MariaDB readiness check (PowerShell — no Python required on target)
Source: "wait_for_db.ps1"; DestDir: "{tmp}"; Flags: deleteafterinstall

; AirTrack bundle (built by build.bat)
Source: "dist\AirTrack\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[INI]
; Write airtrack.cfg to the install directory.
; service.py reads this before importing the Flask app.
Filename: "{app}\airtrack.cfg"; Section: "database"; Key: "uri";      String: "mysql+pymysql://airtrack:Gate1UserPass!@127.0.0.1:3307/airtrack?charset=utf8mb4"
Filename: "{app}\airtrack.cfg"; Section: "database"; Key: "host";     String: "127.0.0.1"
Filename: "{app}\airtrack.cfg"; Section: "database"; Key: "port";     String: "3307"
Filename: "{app}\airtrack.cfg"; Section: "database"; Key: "name";     String: "airtrack"
Filename: "{app}\airtrack.cfg"; Section: "database"; Key: "user";     String: "airtrack"
Filename: "{app}\airtrack.cfg"; Section: "database"; Key: "password"; String: "Gate1UserPass!"
Filename: "{app}\airtrack.cfg"; Section: "app";      Key: "secret_key"; String: "change-me-before-production"
Filename: "{app}\airtrack.cfg"; Section: "app";      Key: "role";     String: "client"

[Run]
; Step 1 — Install MariaDB silently on port 3307
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\mariadb-11.4-winx64.msi"" /quiet /norestart SERVICENAME=AirTrackDB PORT=3307 PASSWORD=Gate1RootPass! ALLOWREMOTEMACHINE=0 BUFFERPOOLSIZE=64 DATADIR=C:\AirTrackData\"; StatusMsg: "Installing MariaDB..."; Flags: waituntilterminated

; Step 2 — Wait for MariaDB to accept connections
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NonInteractive -File ""{tmp}\wait_for_db.ps1"""; StatusMsg: "Waiting for database..."; Flags: waituntilterminated

; Step 3 — Create database, user, and load schema
Filename: "{tmp}\init_db.bat"; StatusMsg: "Initialising database..."; Flags: waituntilterminated

; Step 4 — Install AirTrack service (registers as Automatic / Delayed)
Filename: "{app}\AirTrack.exe"; Parameters: "install"; StatusMsg: "Installing AirTrack service..."; Flags: waituntilterminated

; Step 5 — Set service dependency: AirTrack waits for AirTrackDB on every boot
Filename: "sc.exe"; Parameters: "config AirTrackClient depend= AirTrackDB"; StatusMsg: "Configuring service dependency..."; Flags: waituntilterminated

; Step 6 — Start AirTrack
Filename: "{app}\AirTrack.exe"; Parameters: "start"; StatusMsg: "Starting AirTrack..."; Flags: waituntilterminated

; Step 7 — Open browser (post-install, skipped in silent mode)
Filename: "http://localhost:5000"; Flags: shellexec nowait postinstall skipifsilent; Description: "Open AirTrack in browser"
