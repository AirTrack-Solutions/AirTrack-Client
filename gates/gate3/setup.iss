; AirTrack Windows Installer
; Gate 3 — full installer with per-customer config
;
; BUILD:
;   Automated via .github/workflows/build-windows.yml
;   Requires mariadb-11.4.12-winx64.msi in gates\gate3\ at build time
;
; DEPLOY:
;   AirTrack-Admin packages AirTrackSetup.exe + airtrack.cfg + license.lic
;   Customer extracts zip and runs AirTrackSetup.exe

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
; MariaDB MSI — bundled, extracted to temp and deleted after install
Source: "mariadb-11.4.12-winx64.msi"; DestDir: "{tmp}"; Flags: deleteafterinstall

; MariaDB readiness check
Source: "wait_for_db.ps1"; DestDir: "{tmp}"; Flags: deleteafterinstall

; AirTrack schema — used on fresh installs only
Source: "schema.sql"; DestDir: "{tmp}"; Flags: deleteafterinstall

; AirTrack bundle (built by build.bat / GitHub Actions)
Source: "dist\AirTrack\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Run]
; Step 1 — Install MariaDB silently (skipped if already present)
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\mariadb-11.4.12-winx64.msi"" /quiet /norestart SERVICENAME=AirTrackDB PORT=3307 PASSWORD=AirTrackRoot2024! ALLOWREMOTEMACHINE=0 BUFFERPOOLSIZE=64 DATADIR=C:\AirTrackData\"; StatusMsg: "Installing MariaDB..."; Flags: waituntilterminated; Check: MariaDBNotInstalled

; Step 2 — Wait for MariaDB to accept connections
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NonInteractive -File ""{tmp}\wait_for_db.ps1"""; StatusMsg: "Waiting for database..."; Flags: waituntilterminated

; Step 3 — Init database (written dynamically by [Code] from sidecar airtrack.cfg)
Filename: "cmd.exe"; Parameters: "/c ""{tmp}\init_db.bat"""; StatusMsg: "Initialising database..."; Flags: waituntilterminated

; Step 4 — Install AirTrack as Windows service
Filename: "{app}\AirTrack.exe"; Parameters: "install"; StatusMsg: "Installing AirTrack service..."; Flags: waituntilterminated

; Step 5 — Service dependency: AirTrack waits for MariaDB on every boot
Filename: "sc.exe"; Parameters: "config AirTrackClient depend= AirTrackDB"; StatusMsg: "Configuring service dependency..."; Flags: waituntilterminated

; Step 6 — Start AirTrack
Filename: "{app}\AirTrack.exe"; Parameters: "start"; StatusMsg: "Starting AirTrack..."; Flags: waituntilterminated

; Step 7 — Open browser (interactive installs only)
Filename: "http://localhost:5000"; Flags: shellexec nowait postinstall skipifsilent; Description: "Open AirTrack in browser"

[Code]
const
  MARIADB_ROOT_PASS = 'AirTrackRoot2024!';
  MARIADB_BIN = 'C:\Program Files\MariaDB 11.4\bin\mysql.exe';
  DQ = '"';

{ Skip MariaDB MSI install if already present }
function MariaDBNotInstalled: Boolean;
begin
  Result := not FileExists(MARIADB_BIN);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  CfgFile: String;
  DbUser, DbPass, DbName, DbPort: String;
  SqlContent, BatchContent: String;
  SqlFile, BatchFile: String;
  LicSrc, LicDest: String;
  IsFreshInstall: Boolean;
begin
  { ssInstall fires before files are copied — write helper scripts to {tmp} }
  if CurStep = ssInstall then
  begin
    CfgFile := ExpandConstant('{src}\airtrack.cfg');

    { Read per-customer credentials from sidecar airtrack.cfg }
    DbUser := GetIniString('database', 'user',     'airtrack', CfgFile);
    DbPass := GetIniString('database', 'password', '',         CfgFile);
    DbName := GetIniString('database', 'name',     'airtrack', CfgFile);
    DbPort := GetIniString('database', 'port',     '3307',     CfgFile);

    IsFreshInstall := not FileExists(ExpandConstant('{app}\airtrack.cfg'));

    { Build idempotent DB + user creation SQL }
    SqlContent :=
      'CREATE DATABASE IF NOT EXISTS `' + DbName + '` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;' + #13#10 +
      'CREATE USER IF NOT EXISTS ''' + DbUser + '''@''127.0.0.1'' IDENTIFIED BY ''' + DbPass + ''';' + #13#10 +
      'GRANT ALL PRIVILEGES ON `' + DbName + '`.* TO ''' + DbUser + '''@''127.0.0.1'';' + #13#10 +
      'FLUSH PRIVILEGES;';

    SqlFile := ExpandConstant('{tmp}\init_db.sql');
    SaveStringToFile(SqlFile, SqlContent, False);

    { Build init_db.bat using per-customer credentials }
    BatchContent :=
      '@echo off' + #13#10 +
      DQ + MARIADB_BIN + DQ + ' --port=' + DbPort +
        ' --host=127.0.0.1 --user=root --password=' + MARIADB_ROOT_PASS +
        ' < ' + DQ + SqlFile + DQ + #13#10 +
      'if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%' + #13#10;

    { Only load schema on fresh installs — migrations handle upgrades }
    if IsFreshInstall then
      BatchContent := BatchContent +
        DQ + MARIADB_BIN + DQ + ' --port=' + DbPort +
          ' --host=127.0.0.1 --user=' + DbUser + ' --password=' + DbPass +
          ' ' + DbName + ' < ' + DQ + ExpandConstant('{tmp}\schema.sql') + DQ + #13#10 +
        'if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%' + #13#10;

    BatchFile := ExpandConstant('{tmp}\init_db.bat');
    SaveStringToFile(BatchFile, BatchContent, False);
  end;

  { ssPostInstall fires after files are copied and [Run] items complete }
  if CurStep = ssPostInstall then
  begin
    { Copy sidecar airtrack.cfg — preserve on reinstall }
    if not FileExists(ExpandConstant('{app}\airtrack.cfg')) then
      FileCopy(ExpandConstant('{src}\airtrack.cfg'), ExpandConstant('{app}\airtrack.cfg'), False);

    { Copy sidecar license.lic }
    LicSrc  := ExpandConstant('{src}\license.lic');
    LicDest := ExpandConstant('{app}\_internal\app\config\license.lic');
    if FileExists(LicSrc) then
      FileCopy(LicSrc, LicDest, False);

    { Create runtime data directory structure }
    CreateDir('C:\ProgramData\AirTrack');
    CreateDir('C:\ProgramData\AirTrack\logs');
    CreateDir('C:\ProgramData\AirTrack\backups');
    CreateDir('C:\ProgramData\AirTrack\core');
    CreateDir('C:\ProgramData\AirTrack\packages');

    { Copy core verification files from bundle }
    FileCopy(
      ExpandConstant('{app}\_internal\app\core\airtrack_solutions.pub'),
      'C:\ProgramData\AirTrack\core\airtrack_solutions.pub', False
    );
    FileCopy(
      ExpandConstant('{app}\_internal\app\core\package_installer.py'),
      'C:\ProgramData\AirTrack\core\package_installer.py', False
    );
  end;
end;
