; Inno Setup script for publishing Canvas-AI.
; 1) Build the standalone exe first:  powershell -File windows\build.ps1
; 2) Install Inno Setup (https://jrsoftware.org/isdl.php)
; 3) Compile:  iscc windows\installer.iss   ->  dist\Canvas-AI-Setup.exe
;
; The exe is already self-contained (backend + login/quiz browser bundled), so
; the installer just places it and makes shortcuts. Each user installs Claude
; Code and signs in from the app's Setup tab on first run.

#define MyApp "Canvas-AI"
#define MyVer "0.1.0"
#define MyPublisher "Canvas-AI"

[Setup]
AppName={#MyApp}
AppVersion={#MyVer}
AppPublisher={#MyPublisher}
VersionInfoVersion={#MyVer}
DefaultDirName={autopf}\Canvas-AI
DefaultGroupName=Canvas-AI
OutputDir=..\dist
OutputBaseFilename=Canvas-AI-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
SetupIconFile=CanvasAI.ico
UninstallDisplayIcon={app}\CanvasAI.exe
DisableProgramGroupPage=yes

[Files]
Source: "..\dist\CanvasAI.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Canvas-AI"; Filename: "{app}\CanvasAI.exe"
Name: "{autodesktop}\Canvas-AI"; Filename: "{app}\CanvasAI.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\CanvasAI.exe"; Description: "Launch Canvas-AI"; Flags: nowait postinstall skipifsilent
