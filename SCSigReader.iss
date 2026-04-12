; SC Signature Reader – Inno Setup Script
; Build: iscc SCSigReader.iss

#define AppName    "SC Signature Reader"
#define AppVersion "1.0"
#define AppExe     "SCSigReader.exe"
#define Publisher  "Seneca0815"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
DefaultDirName={autopf}\SCSigReader
DefaultGroupName={#AppName}
OutputBaseFilename=SCSigReader_Setup_{#AppVersion}
OutputDir=installer
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
WizardImageFile=vargo_installer.bmp
WizardSmallImageFile=vargo_installer_header.bmp
SetupIconFile=vargo_icon.ico
UninstallDisplayIcon={app}\{#AppExe}
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Registry]
; Add Tesseract to the system PATH so it is available to all applications.
; NeedsAddPath() (defined in [Code] below) prevents duplicate entries.
Root: HKLM; \
  Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; \
  ValueType: expandsz; ValueName: "Path"; \
  ValueData: "{olddata};C:\Program Files\Tesseract-OCR"; \
  Check: NeedsAddPath('C:\Program Files\Tesseract-OCR')

[Files]
; Main executable (built with PyInstaller)
Source: "dist\{#AppExe}";             DestDir: "{app}"; Flags: ignoreversion

; Data files
Source: "config.json";                DestDir: "{app}"; Flags: ignoreversion
Source: "lookup.json";                DestDir: "{app}"; Flags: ignoreversion
Source: "themes.py";                  DestDir: "{app}"; Flags: ignoreversion
Source: "theme_preview.png";          DestDir: "{app}"; Flags: ignoreversion

; Brand assets
Source: "vargo_icon.ico";            DestDir: "{app}"; Flags: ignoreversion
Source: "vargo_icon_256.png";        DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; Tesseract installer (bundled in redist\ folder)
Source: "redist\tesseract-setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Run]
; 1. Install Tesseract silently
Filename: "{tmp}\tesseract-setup.exe"; \
  Parameters: "/S /D=C:\Program Files\Tesseract-OCR"; \
  StatusMsg: "Installing Tesseract OCR..."; \
  Flags: waituntilterminated

; 2. Patch tesseract_cmd in config.json after Tesseract is installed
Filename: "powershell.exe"; \
  Parameters: "-Command ""(Get-Content '{app}\config.json') -replace 'tesseract', 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe' | Set-Content '{app}\config.json'"""; \
  Flags: runhidden waituntilterminated

; 3. Launch setup wizard on first start
Filename: "{app}\{#AppExe}"; \
  Parameters: "--setup"; \
  StatusMsg: "Starting setup wizard..."; \
  Flags: nowait

[Icons]
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall";            Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}";   Filename: "{app}\{#AppExe}"; IconFilename: "{app}\vargo_icon.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[UninstallDelete]
Type: files; Name: "{app}\config.json"

[Code]
{ Returns True when Dir is not already present in the system PATH,
  so the [Registry] entry is only written when actually needed. }
function NeedsAddPath(Dir: string): Boolean;
var
  CurrentPath: string;
begin
  if not RegQueryStringValue(
      HKEY_LOCAL_MACHINE,
      'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
      'Path', CurrentPath)
  then begin
    Result := True;
    Exit;
  end;
  Result := Pos(';' + Lowercase(Dir) + ';',
                ';' + Lowercase(CurrentPath) + ';') = 0;
end;

{ Broadcast WM_SETTINGCHANGE so the new PATH is picked up by Explorer and
  any already-running processes without requiring a reboot. }
procedure CurStepChanged(CurStep: TSetupStep);
var
  Dummy: DWORD;
begin
  if CurStep = ssPostInstall then
    SendBroadcastMessage(WM_SETTINGCHANGE, 0, 'Environment', Dummy);
end;
