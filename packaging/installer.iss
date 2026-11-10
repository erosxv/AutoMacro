; Instalador do AutoMacro (Inno Setup 6). Gerado pelo GitHub Actions:
;   ISCC.exe /DAppVersion=0.1.12 packaging\installer.iss  ->  dist\AutoMacro-Setup.exe
; Instala só para o usuário atual (sem pedir administrador), o que permite à atualização
; automática do app instalar a versão nova em silêncio.

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{B7E2C1A4-5D3F-4E8A-9C61-2F0A7D4E9B13}
AppName=AutoMacro
AppVersion={#AppVersion}
AppVerName=AutoMacro {#AppVersion}
AppPublisher=Eros
DefaultDirName={autopf}\AutoMacro
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=AutoMacro-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\AutoMacro.exe
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\AutoMacro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\AutoMacro"; Filename: "{app}\AutoMacro.exe"
Name: "{autodesktop}\AutoMacro"; Filename: "{app}\AutoMacro.exe"; Tasks: desktopicon

[Run]
; Instalação normal: oferece abrir o programa ao final.
Filename: "{app}\AutoMacro.exe"; Description: "Abrir o AutoMacro"; Flags: nowait postinstall skipifsilent
; Atualização automática (silenciosa, iniciada pelo próprio app com /RELAUNCH=1): reabre o programa.
Filename: "{app}\AutoMacro.exe"; Flags: nowait runasoriginaluser; Check: ShouldRelaunch

[Code]
function ShouldRelaunch: Boolean;
begin
  Result := ExpandConstant('{param:RELAUNCH|0}') = '1';
end;
