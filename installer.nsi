; PermaDesign Installer
; Built with NSIS 3.x

!include "MUI2.nsh"
!include "LogicLib.nsh"

; General
Name "PermaDesign"
OutFile "PermaDesign-Installer.exe"
InstallDir "$PROGRAMFILES\PermaDesign"

RequestExecutionLevel admin

; MUI Settings
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

; Installer sections
Section "PermaDesign"
  SetOutPath "$INSTDIR"
  File /r "dist\PermaDesign\*.*"

  ; Create desktop shortcut
  CreateShortCut "$DESKTOP\PermaDesign.lnk" "$INSTDIR\PermaDesign.exe"

  ; Create start menu shortcut
  CreateDirectory "$SMPROGRAMS\PermaDesign"
  CreateShortCut "$SMPROGRAMS\PermaDesign\PermaDesign.lnk" "$INSTDIR\PermaDesign.exe"
  CreateShortCut "$SMPROGRAMS\PermaDesign\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

; Create uninstaller
Section "Uninstall"
  RMDir /r "$INSTDIR"
  RMDir /r "$SMPROGRAMS\PermaDesign"
  Delete "$DESKTOP\PermaDesign.lnk"
SectionEnd
