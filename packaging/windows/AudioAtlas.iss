#ifndef MyAppVersion
  #error MyAppVersion must be defined
#endif
#ifndef MyBuildNumber
  #error MyBuildNumber must be defined
#endif
#ifndef SourceDir
  #error SourceDir must be defined
#endif
#ifndef OutputDir
  #error OutputDir must be defined
#endif
#ifndef OutputBaseFilename
  #error OutputBaseFilename must be defined
#endif

[Setup]
AppId={{A86D17D8-C2B9-4F05-9F47-88B693CA41AE}
AppName=AudioAtlas
AppVersion={#MyAppVersion}
AppVerName=AudioAtlas {#MyAppVersion} (internal build {#MyBuildNumber})
AppPublisher=Charles Mish
AppPublisherURL=https://github.com/CharlesMish/AudioAtlas
AppSupportURL=https://github.com/CharlesMish/AudioAtlas/issues
DefaultDirName={localappdata}\Programs\AudioAtlas
DefaultGroupName=AudioAtlas
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
SetupArchitecture=x64
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.19045
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=no
ChangesEnvironment=no
CloseApplications=yes
CloseApplicationsFilter=AudioAtlas.exe
UninstallDisplayIcon={app}\AudioAtlas.exe
VersionInfoVersion=0.2.0.7
VersionInfoDescription=AudioAtlas internal Windows candidate
VersionInfoProductName=AudioAtlas
VersionInfoProductVersion={#MyAppVersion}

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Icons]
Name: "{autoprograms}\AudioAtlas"; Filename: "{app}\AudioAtlas.exe"
Name: "{autodesktop}\AudioAtlas"; Filename: "{app}\AudioAtlas.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AudioAtlas.exe"; Description: "Launch AudioAtlas"; Flags: nowait postinstall skipifsilent
