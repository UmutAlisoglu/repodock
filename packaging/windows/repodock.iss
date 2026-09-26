; Inno Setup script for the repodock Windows installer.
; Built by .github/workflows/windows.yml: iscc /DAppVersion=x.y.z repodock.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F3C2B8E-4D1A-4E7B-9C55-2A1D7E0B9F41}
AppName=repodock
AppVersion={#AppVersion}
AppVerName=repodock {#AppVersion}
AppPublisher=UmutAlisoglu
AppPublisherURL=https://github.com/UmutAlisoglu/repodock
AppSupportURL=https://github.com/UmutAlisoglu/repodock/issues
DefaultDirName={localappdata}\Programs\repodock
DefaultGroupName=repodock
DisableProgramGroupPage=yes
; No admin rights needed: installs for the current user only.
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=repodock-setup
SetupIconFile=repodock.ico
UninstallDisplayIcon={app}\repodock.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\..\dist\repodock\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\repodock"; Filename: "{app}\repodock.exe"; Comment: "Download GitHub projects and run them from a dashboard"
Name: "{autodesktop}\repodock"; Filename: "{app}\repodock.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\repodock.exe"; Description: "Start repodock now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
