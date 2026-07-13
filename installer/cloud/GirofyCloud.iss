#define MyAppName "Girofy"
#define MyAppExeName "Girofy.exe"
#define MyAppPublisher "Girofy"
#define MyAppVersion GetEnv("APP_VERSION")

#if MyAppVersion == ""
#define MyAppVersion "1.0.0"
#endif

[Setup]
AppId={{7C56B7B6-33B9-47C5-B7A9-59C3F2F1C7E0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Girofy
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=Girofy-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\..\desktop_cloud\resources\girofy.ico

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "..\..\dist\Girofy\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\desktop_cloud\resources\desktop.json"; DestDir: "{commonappdata}\Girofy\config"; DestName: "desktop.json"; Flags: ignoreversion onlyifdoesntexist uninsneveruninstall

[Dirs]
Name: "{commonappdata}\Girofy\config"
Name: "{commonappdata}\Girofy\logs"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: checkedonce

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
