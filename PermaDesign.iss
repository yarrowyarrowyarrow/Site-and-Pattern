[Setup]
AppName=PermaDesign
AppVersion=1.6.1
AppPublisher=PermaDesign
AppComments=Permaculture landscape design tool
DefaultDirName={autopf}\PermaDesign
DefaultGroupName=PermaDesign
OutputDir=dist
OutputBaseFilename=PermaDesign-Setup
PrivilegesRequired=lowest
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "dist\PermaDesign\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PermaDesign"; Filename: "{app}\PermaDesign.exe"
Name: "{group}\Uninstall PermaDesign"; Filename: "{uninstallexe}"
Name: "{autodesktop}\PermaDesign"; Filename: "{app}\PermaDesign.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PermaDesign.exe"; Description: "Launch PermaDesign now"; Flags: nowait postinstall skipifsilent
