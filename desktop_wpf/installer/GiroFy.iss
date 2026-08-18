#ifndef AppVersion
  #error AppVersion must be provided by build-installer.ps1
#endif

#ifndef PublishDir
  #define PublishDir "..\artifacts\Girofy-Windows-WPF"
#endif

#ifndef OutputDir
  #define OutputDir "..\artifacts\installer"
#endif

#define AppName "GiroFy"
#define AppExeName "Girofy.exe"

[Setup]
AppId={{4A79774E-9F9D-4CB5-84A6-69BF567BE89B}
AppName={#AppName}
AppVersion={#AppVersion}
VersionInfoVersion={#AppVersion}
VersionInfoProductVersion={#AppVersion}
VersionInfoDescription=Instalador de desenvolvimento do GiroFy Windows
DefaultDirName={localappdata}\Programs\GiroFy
DefaultGroupName=GiroFy
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=GiroFy-Setup-{#AppVersion}
SetupIconFile=..\src\Girofy.Desktop\Resources\Girofy.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName=GiroFy
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

[Icons]
Name: "{userprograms}\GiroFy"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExeName}"
Name: "{userdesktop}\GiroFy"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Abrir o GiroFy"; Flags: nowait postinstall skipifsilent
