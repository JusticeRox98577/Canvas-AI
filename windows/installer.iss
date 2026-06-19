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

[Code]
var
  InfoPage: TInputQueryWizardPage;
  BrainPage: TInputOptionWizardPage;

procedure InitializeWizard;
begin
  InfoPage := CreateInputQueryPage(wpSelectDir,
    'Set up Canvas-AI',
    'Enter your details. You can change all of these later in the app''s Settings.',
    'These are saved to your Canvas-AI profile on this PC. Leave the license key blank if you don''t have one yet.');
  InfoPage.Add('License key:', False);
  InfoPage.Add('Canvas URL (e.g. https://yourschool.instructure.com):', False);

  BrainPage := CreateInputOptionPage(InfoPage.ID,
    'AI brain', 'Which AI should power studying?',
    'You can change this later in Settings.', True, False);
  BrainPage.Add('Claude  (your Claude Pro/Max subscription)');
  BrainPage.Add('Ollama  (free, runs locally)');
  BrainPage.Add('Anthropic  (paid API key)');
  BrainPage.SelectedValueIndex := 0;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Url: String;
begin
  Result := True;
  if CurPageID = InfoPage.ID then
  begin
    Url := Trim(InfoPage.Values[1]);
    if (Url <> '') and (Lowercase(Copy(Url, 1, 7)) <> 'http://')
       and (Lowercase(Copy(Url, 1, 8)) <> 'https://') then
    begin
      MsgBox('Please enter a full Canvas URL starting with https:// '
        + '(for example https://yourschool.instructure.com), '
        + 'or leave it blank to set it later in the app.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

function BrainValue(): String;
begin
  if BrainPage.SelectedValueIndex = 1 then
    Result := 'ollama'
  else if BrainPage.SelectedValueIndex = 2 then
    Result := 'anthropic'
  else
    Result := 'claude_code';
end;

function JsonEscape(const S: String): String;
var
  R: String;
begin
  R := S;
  StringChangeEx(R, '\', '\\', True);
  StringChangeEx(R, '"', '\"', True);
  Result := R;
end;

procedure WriteUserConfig();
var
  Dir, SFile, LFile, Url, Key, Brain: String;
begin
  Dir := ExpandConstant('{userappdata}\Canvas-AI');
  ForceDirectories(Dir);
  Key := Trim(InfoPage.Values[0]);
  Url := Trim(InfoPage.Values[1]);
  Brain := BrainValue();

  SFile := Dir + '\settings.json';
  if not FileExists(SFile) then
    SaveStringToFile(SFile,
      '{' + #13#10 +
      '  "canvas_base_url": "' + JsonEscape(Url) + '",' + #13#10 +
      '  "llm_provider": "' + Brain + '",' + #13#10 +
      '  "draft_provider": "' + Brain + '"' + #13#10 +
      '}', False);

  LFile := Dir + '\license.json';
  if (Key <> '') and (not FileExists(LFile)) then
    SaveStringToFile(LFile, '{ "key": "' + JsonEscape(Key) + '" }', False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    WriteUserConfig();
end;
