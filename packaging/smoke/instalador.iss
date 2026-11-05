; Instalador de la prueba de humo. Por usuario, sin permisos de administrador.
#define AppName "TalentCV Smoke"
#define AppVersion "0.0.1"

[Setup]
AppId={{7B1E5A52-3D0C-4E0B-9F57-6B2A4C1D8E01}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\TalentCVSmoke
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\output\installer
OutputBaseFilename=TalentCVSmoke-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "..\output\dist\TalentCVSmoke\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\TalentCVSmoke.exe"

[Run]
Filename: "{app}\TalentCVSmoke.exe"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent
