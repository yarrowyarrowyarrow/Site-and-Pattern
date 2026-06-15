; Site & Pattern Installer
; Built with NSIS 3.x
; Display name is "Site & Pattern"; the bundled artifact base name is the
; script-safe "SiteAndPattern" (matches permadesign.spec).

!include "MUI2.nsh"
!include "LogicLib.nsh"

; General
Name "Site & Pattern"
OutFile "SiteAndPattern-Installer.exe"
InstallDir "$PROGRAMFILES\Site & Pattern"

RequestExecutionLevel admin

; MUI Settings
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

; Installer sections
Section "Site & Pattern"
  SetOutPath "$INSTDIR"
  File /r "dist\SiteAndPattern\*.*"

  ; Create desktop shortcut
  CreateShortCut "$DESKTOP\Site & Pattern.lnk" "$INSTDIR\SiteAndPattern.exe"

  ; Create start menu shortcut
  CreateDirectory "$SMPROGRAMS\Site & Pattern"
  CreateShortCut "$SMPROGRAMS\Site & Pattern\Site & Pattern.lnk" "$INSTDIR\SiteAndPattern.exe"
  CreateShortCut "$SMPROGRAMS\Site & Pattern\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

; Create uninstaller
Section "Uninstall"
  RMDir /r "$INSTDIR"
  RMDir /r "$SMPROGRAMS\Site & Pattern"
  Delete "$DESKTOP\Site & Pattern.lnk"
SectionEnd
