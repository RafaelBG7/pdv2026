#ifndef AppVersion
  #error AppVersion must be provided by build-installer.ps1
#endif

#ifndef PublishDir
  #define PublishDir "..\artifacts\SkyGest-Windows-WPF"
#endif

#ifndef OutputDir
  #define OutputDir "..\artifacts\installer"
#endif

#define AppName "SkyGest"
#define AppExeName "SkyGest.exe"

[Setup]
AppId={{4A79774E-9F9D-4CB5-84A6-69BF567BE89B}
AppName={#AppName}
AppVersion={#AppVersion}
VersionInfoVersion={#AppVersion}
VersionInfoProductVersion={#AppVersion}
VersionInfoDescription=Instalador de desenvolvimento do SkyGest Windows
DefaultDirName={localappdata}\Programs\SkyGest
DefaultGroupName=SkyGest
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=SkyGest-Setup-{#AppVersion}
SetupIconFile=..\src\Girofy.Desktop\Resources\SkyGest.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName=SkyGest
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes
UsePreviousGroup=yes
ChangesAssociations=no
ChangesEnvironment=no
AllowNoIcons=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: unchecked

[Files]
Source: "{#PublishDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Remove somente binário e atalhos visuais antigos durante o upgrade. Dados locais são preservados.
Type: files; Name: "{app}\Girofy.exe"
Type: files; Name: "{userprograms}\GiroFy.lnk"
Type: files; Name: "{userdesktop}\GiroFy.lnk"

[Icons]
Name: "{userprograms}\SkyGest"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExeName}"
Name: "{userdesktop}\SkyGest"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\girofy"; ValueType: string; ValueData: "URL:SkyGest Protocol"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\girofy"; ValueName: "URL Protocol"; ValueType: string; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\girofy\DefaultIcon"; ValueType: string; ValueData: "{app}\{#AppExeName},0"
Root: HKCU; Subkey: "Software\Classes\girofy\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExeName}"" ""%1"""

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Abrir o SkyGest"; Flags: nowait postinstall skipifsilent
