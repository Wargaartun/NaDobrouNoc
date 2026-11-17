; Instalátor pro Windows (Inno Setup 6).
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DVerze=0.6.0 baleni\windows\NaDobrouNoc.iss
; Předpoklad: složka dist\NaDobrouNoc z PyInstalleru (baleni\na_dobrou_noc.spec).
;
; Instalace jen pro aktuálního uživatele – nepotřebuje práva správce a nespouští dotaz UAC.
; Data aplikace (%APPDATA%\NaDobrouNoc) odinstalace nemaže, aby nové instalace o nic nepřišly.

#ifndef Verze
  #define Verze "0.0.0"
#endif

[Setup]
; AppId se nesmí měnit – podle něj Windows poznají, že jde o aktualizaci téže aplikace.
AppId={{B249AC1E-538E-433D-8AD8-7DBDFA7EF01A}
AppName=Na dobrou noc
AppVersion={#Verze}
AppVerName=Na dobrou noc {#Verze}
AppPublisher=Projekt Na dobrou noc
AppPublisherURL=https://github.com/Wargaartun/NaDobrouNoc
AppSupportURL=https://github.com/Wargaartun/NaDobrouNoc/issues
AppUpdatesURL=https://github.com/Wargaartun/NaDobrouNoc/releases
DefaultDirName={autopf}\NaDobrouNoc
DefaultGroupName=Na dobrou noc
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=NaDobrouNoc-{#Verze}-instalator
SetupIconFile=..\ikona.ico
UninstallDisplayIcon={app}\NaDobrouNoc.exe
UninstallDisplayName=Na dobrou noc
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; běžící aplikaci před aktualizací nebo odinstalací zavře (Restart Manager)
CloseApplications=yes
CloseApplicationsFilter=NaDobrouNoc.exe
VersionInfoVersion={#Verze}
VersionInfoProductName=Na dobrou noc

[Languages]
Name: "cs"; MessagesFile: "compiler:Languages\Czech.isl"

[Tasks]
Name: "plocha"; Description: "Vytvořit ikonu na ploše"; GroupDescription: "Ikony:"

[Files]
Source: "..\..\dist\NaDobrouNoc\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; staré soubory programu z předchozí verze (data v %APPDATA% zůstávají)
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\Na dobrou noc"; Filename: "{app}\NaDobrouNoc.exe"
Name: "{group}\Odinstalovat Na dobrou noc"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Na dobrou noc"; Filename: "{app}\NaDobrouNoc.exe"; Tasks: plocha

[Run]
Filename: "{app}\NaDobrouNoc.exe"; Description: "Spustit Na dobrou noc"; Flags: nowait postinstall skipifsilent
