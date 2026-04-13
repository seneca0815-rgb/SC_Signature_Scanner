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
; Add Tesseract bin directory to PATH so tesseract.exe and its DLLs are
; found by all applications. NeedsAddPath() prevents duplicate entries.
Root: HKLM; \
  Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; \
  ValueType: expandsz; ValueName: "Path"; \
  ValueData: "{olddata};C:\Program Files\Tesseract-OCR"; \
  Check: NeedsAddPath('C:\Program Files\Tesseract-OCR')

; TESSDATA_PREFIX tells Tesseract where to find language/model data when
; it cannot determine the path from its own executable location (e.g. when
; called from a frozen exe or a non-standard working directory).
; Tesseract 5.x requires this to point at the tessdata/ subfolder, not the
; Tesseract-OCR install root.
Root: HKLM; \
  Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; \
  ValueType: expandsz; ValueName: "TESSDATA_PREFIX"; \
  ValueData: "C:\Program Files\Tesseract-OCR\tessdata"

[Files]
; Main executable (built with PyInstaller)
Source: "dist\{#AppExe}";             DestDir: "{app}"; Flags: ignoreversion

; Data files
Source: "config.json";                DestDir: "{app}"; Flags: ignoreversion
Source: "lookup.json";                DestDir: "{app}"; Flags: ignoreversion
Source: "themes.py";                  DestDir: "{app}"; Flags: ignoreversion
Source: "theme_preview.png";          DestDir: "{app}"; Flags: ignoreversion
Source: "logger_setup.py";            DestDir: "{app}"; Flags: ignoreversion

; Brand assets
Source: "vargo_icon.ico";            DestDir: "{app}"; Flags: ignoreversion
Source: "vargo_icon_256.png";        DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; Sound files
Source: "sounds\init.wav";        DestDir: "{app}\sounds"; Flags: ignoreversion
Source: "sounds\activate.wav";    DestDir: "{app}\sounds"; Flags: ignoreversion
Source: "sounds\deactivate.wav";  DestDir: "{app}\sounds"; Flags: ignoreversion
Source: "sounds\signal.wav";      DestDir: "{app}\sounds"; Flags: ignoreversion

; Tesseract installer (bundled in redist\ folder)
Source: "redist\tesseract-setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Run]
; 1. Install Tesseract silently
Filename: "{tmp}\tesseract-setup.exe"; \
  Parameters: "/S /D=C:\Program Files\Tesseract-OCR"; \
  StatusMsg: "Installing Tesseract OCR..."; \
  Flags: waituntilterminated

; 2. Patch tesseract_cmd value in config.json after Tesseract is installed.
; Uses ConvertFrom-Json / ConvertTo-Json to avoid corrupting other keys.
Filename: "powershell.exe"; \
  Parameters: "-Command ""$c = Get-Content '{app}\config.json' -Raw | ConvertFrom-Json; $c.tesseract_cmd = 'C:\Program Files\Tesseract-OCR\tesseract.exe'; $c | ConvertTo-Json -Depth 10 | Set-Content '{app}\config.json'"""; \
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
Type: files;          Name: "{app}\config.json"
Type: filesandordirs; Name: "{userappdata}\VargoDynamics\SCSigReader\logs"

[Code]
const
  WM_SETTINGCHANGE  = 26;   { not predefined in Inno Setup Pascal }
  SMTO_ABORTIFHUNG  = 2;    { HWND_BROADCAST is predefined, omitted }

{ SendBroadcastMessage in Inno Setup Pascal does not accept a string LParam.
  Import SendMessageTimeoutA directly so we can pass 'Environment'.
  Inno Setup Pascal has no UINT/WPARAM/LRESULT aliases — use Cardinal/Integer. }
function SendMessageTimeout(hWnd: Cardinal; Msg: Cardinal; wParam: Cardinal;
  lParam: AnsiString; fuFlags: Cardinal; uTimeout: Cardinal;
  var lpdwResult: DWORD): Integer;
  external 'SendMessageTimeoutA@user32.dll stdcall';

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
    SendMessageTimeout(HWND_BROADCAST, WM_SETTINGCHANGE, 0, 'Environment',
                       SMTO_ABORTIFHUNG, 5000, Dummy);
end;
