;============================================================
;  AirTrack Windows v1.0.0  "Wilbur" – Inno Setup script
;============================================================

#define CERTPWD "marianneanneroxannediane"

[Setup]
AppName=AirTrack Windows
AppVersion=0.9.0
DefaultDirName={code:GetCustomInstallDir}
DefaultGroupName=AirTrack Windows
UninstallDisplayIcon={app}\airtrack_icon.ico
PrivilegesRequired=none
OutputDir=.
OutputBaseFilename=AirTrack-Windows-Installer
Compression=lzma
SolidCompression=yes
; SignTool=airSign   ; (Removed – now handled via PostCompile)
DiskSpanning=yes
DiskSliceSize=2100000000 ; Example: 2GB slices
SlicesPerDisk=2        ; Example: 2 slices per disk
UseSetupLdr=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "AirTrack_full_0.9.0.zip"; DestDir: "{tmp}"; Flags: ignoreversion
Source: "AirTrack_images.tar"; DestDir: "{app}"; Flags: ignoreversion
Source: "AirTrack_images.tar"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "start_airtrack.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "install_airtrack_windows.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "airtrack_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "README-Windows.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "INSTALL.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\AirTrack Windows"; \
  Filename: "{code:GetCustomInstallDir}\start_airtrack.bat"; \
  IconFilename: "{app}\airtrack_icon.ico"

[Run]
Filename: powershell.exe; Parameters: -ExecutionPolicy Bypass -File {app}\install_airtrack_windows.ps1 {tmp}\AirTrack_full_0.9.0.zip; Flags: waituntilterminated shellexec

[Code]
function GetCustomInstallDir(Default: String): String;
var
  userDir: String;
begin
  userDir := GetEnv('USERPROFILE');
  Result := userDir + '\docker\AirTrack-Windows';
end;

[PostCompile]
Cmd="\"C:\\Program Files (x86)\\Windows Kits\\10\\bin\\10.0.22621.0\\x64\\signtool.exe\" sign /f \"C:\\Users\\trevo\\docker\\certs\\AirTrack_Beta.pfx\" /p \"{#CERTPWD}\" /fd sha256 /tr http://timestamp.digicert.com /td sha256 \"AirTrack-Windows-Installer.exe\""

