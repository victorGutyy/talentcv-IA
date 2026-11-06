; Instalador de TalentCV AI. Por usuario (sin permisos de administrador). Se compila con packaging\construir.ps1.
; Los datos del usuario viven en %APPDATA%\TalentCV y NUNCA se tocan al actualizar ni al desinstalar.
#ifndef Version
  #define Version "1.0.0"
#endif
#define NombreApp "TalentCV AI"

[Setup]
AppId={{B3D0C2E4-6B8A-4C53-9C6F-4D2E1A9F7A10}
AppName={#NombreApp}
AppVersion={#Version}
AppPublisher=TalentCV AI
DefaultDirName={autopf}\TalentCV
DefaultGroupName={#NombreApp}
PrivilegesRequired=lowest
OutputDir=output\installer
OutputBaseFilename=TalentCV-Setup-{#Version}
SetupIconFile=vendor\icono.ico
UninstallDisplayIcon={app}\TalentCV.exe
UninstallDisplayName={#NombreApp}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes
VersionInfoVersion={#Version}
VersionInfoDescription=Instalador de {#NombreApp}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Files]
Source: "output\dist\TalentCV\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#NombreApp}"; Filename: "{app}\TalentCV.exe"
Name: "{autodesktop}\{#NombreApp}"; Filename: "{app}\TalentCV.exe"; Tasks: escritorio

[Run]
Filename: "{app}\TalentCV.exe"; Description: "Abrir {#NombreApp}"; Flags: nowait postinstall skipifsilent
; Actualizacion lanzada desde la propia app (instalacion silenciosa con /RELANZAR=1): vuelve a abrirla al terminar.
Filename: "{app}\TalentCV.exe"; Flags: nowait runasoriginaluser; Check: DebeRelanzar

[Code]
function DebeRelanzar: Boolean;
begin
  Result := ExpandConstant('{param:RELANZAR|0}') = '1';
end;

{ WebView2 es lo que dibuja la ventana. Windows 11 lo trae; en Windows 10 puede faltar. }
function WebView2Instalado: Boolean;
var v: String;
begin
  Result := RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v)
         or RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v);
  Result := Result and (v <> '') and (v <> '0.0.0.0');
end;

function InitializeSetup: Boolean;
begin
  Result := True;
  if not WebView2Instalado then
    { SuppressibleMsgBox (no MsgBox): en una instalacion silenciosa no debe quedarse esperando a que alguien pulse un boton. }
    Result := SuppressibleMsgBox('Este equipo no tiene «Microsoft Edge WebView2 Runtime», que TalentCV AI necesita para mostrar su ventana.' + #13#10#13#10 +
                     'Puedes continuar y descargarlo después desde:' + #13#10 + 'https://developer.microsoft.com/microsoft-edge/webview2/' + #13#10#13#10 +
                     '¿Continuar con la instalación?', mbConfirmation, MB_YESNO, IDYES) = IDYES;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    SuppressibleMsgBox('TalentCV AI se desinstaló.' + #13#10#13#10 + 'Tus perfiles, documentos y versiones se conservan en:' + #13#10 +
           ExpandConstant('{userappdata}\TalentCV') + #13#10 + 'Puedes borrar esa carpeta si ya no los necesitas.', mbInformation, MB_OK, IDOK);
end;
