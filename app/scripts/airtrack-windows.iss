;============================================================
;  AirTrack Windows — Inno Setup script
;  Build via: build_airtrack_windows.ps1
;  Do not run ISCC.exe on this file directly.
;============================================================

; Values passed in from build_airtrack_windows.ps1 via /D flags.
; Defaults allow the .iss to be syntax-checked standalone.
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef ZipName
  #define ZipName "AirTrack_full_1.0.0.zip"
#endif

[Setup]
AppName=AirTrack Windows
AppVersion={#AppVersion}
AppPublisher=AirTrack Solutions
AppPublisherURL=https://airtracksolutions.com
DefaultDirName={code:GetInstallDir}
DefaultGroupName=AirTrack Windows
UninstallDisplayIcon={app}\airtrack_icon.ico
PrivilegesRequired=none
OutputDir={#SourcePath}
OutputBaseFilename=AirTrack-Windows-Installer
Compression=lzma2/ultra64
SolidCompression=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Project archive — extracted to {tmp}, then unpacked by the install script.
; deleteafterinstall keeps the final install dir clean.
Source: "{#ZipName}";                   DestDir: "{tmp}";  Flags: ignoreversion deleteafterinstall
; Support files — extracted directly into the install directory.
Source: "AirTrack_images.tar";          DestDir: "{app}";  Flags: ignoreversion
Source: "config.json";                  DestDir: "{app}";  Flags: ignoreversion
Source: "start_airtrack.bat";           DestDir: "{app}";  Flags: ignoreversion
Source: "install_airtrack_windows.ps1"; DestDir: "{app}";  Flags: ignoreversion
Source: "airtrack_icon.ico";            DestDir: "{app}";  Flags: ignoreversion
Source: "LICENSE.txt";                  DestDir: "{app}";  Flags: ignoreversion
Source: "README-Windows.md";            DestDir: "{app}";  Flags: ignoreversion

[Icons]
; Desktop shortcut
Name: "{autodesktop}\AirTrack";         Filename: "{app}\start_airtrack.bat"; IconFilename: "{app}\airtrack_icon.ico"
; Start Menu shortcuts
Name: "{group}\AirTrack";               Filename: "{app}\start_airtrack.bat"; IconFilename: "{app}\airtrack_icon.ico"
Name: "{group}\Uninstall AirTrack";     Filename: "{uninstallexe}"

[Run]
; Run the install script after all files are in place.
; The script handles: Docker check, image load, .env creation, docker compose up.
Filename: powershell.exe; \
  Parameters: "-ExecutionPolicy Bypass -WindowStyle Normal -File ""{app}\install_airtrack_windows.ps1"" ""{tmp}\{#ZipName}"""; \
  Flags: waituntilterminated shellexec; \
  StatusMsg: "Setting up AirTrack — this may take a few minutes..."

[Code]
{ Install into %USERPROFILE%\docker\AirTrack-Windows by default. }
function GetInstallDir(Default: String): String;
begin
  Result := GetEnv('USERPROFILE') + '\docker\AirTrack-Windows';
end;
