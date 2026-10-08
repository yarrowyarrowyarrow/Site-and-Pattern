; Site & Pattern Installer
; Built with NSIS 3.x
; Display name is "Site & Pattern"; the bundled artifact base name is the
; script-safe "SiteAndPattern" (matches scripts/packaging/permadesign.spec).
; NSIS chdir's to this .nsi file's own directory before processing, so the
; File/OutFile paths below are relative to scripts/packaging/ — "..\.." reaches
; the repo root, where PyInstaller wrote dist/ and where the workflow expects
; SiteAndPattern-Installer.exe.
;
; UPDATE MODE (V3.15, F228). Help -> Check for Updates runs this installer as
;     SiteAndPattern-V3.xx-Setup.exe /UPDATE /D=<the folder the app runs from>
; and then closes the app. With /UPDATE the folder and finish pages are
; skipped: the installer waits for the app to let go of its files, replaces
; the program, closes itself and opens Site & Pattern again. Windows will not
; let a running program's files be opened for writing, which is the "Error
; opening file for writing" an update stopped on until V3.15, when the app
; started this and stayed open. The switch is spelled once in
; src/github_releases.py (UPDATE_SWITCH); tests/test_installer_script.py keeps
; the two equal.

Unicode true

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

; General
Name "Site & Pattern"
OutFile "..\..\SiteAndPattern-Installer.exe"
InstallDir "$PROGRAMFILES\Site & Pattern"
!define REG_KEY "Software\Site & Pattern"
; A later install run by hand proposes the folder the last one used.
InstallDirRegKey HKLM "${REG_KEY}" "InstallDir"

RequestExecutionLevel admin

; A file that cannot be written is Abort or Retry, never Ignore. Ignoring a
; locked SiteAndPattern.exe kept the old program (its code is inside the exe)
; while the loose version.txt beside it was replaced, so the old program
; reported the new version and Check for Updates called it up to date.
AllowSkipFiles off

!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Site & Pattern"
!define APP_EXE "SiteAndPattern.exe"
; The map's web engine is a second program, and lets go of the files a
; moment after the first. Where PyInstaller puts it: PyQt6/Qt6 plus the Qt
; wheel's own folder, which on Windows is bin (read from the 6.11 wheel in
; V3.15). A wrong path would only skip this half of the check.
!define WEB_ENGINE_EXE "_internal\PyQt6\Qt6\bin\QtWebEngineProcess.exe"
!define STILL_OPEN "Site & Pattern is still open (or still closing).$\r$\n$\r$\nSave your design and close Site & Pattern, then click Retry."
; How long update mode waits for the app to close, in half-second checks,
; before asking: a minute. (Settable at build time so a test need not wait.)
!define /ifndef WAIT_CHECKS 120

; The version shown in Settings -> Apps, from the version.txt the build
; scripts write beside dist/ before PyInstaller runs.
!if /FileExists "..\..\version.txt"
  !searchparse /noerrors /file "..\..\version.txt" "" APP_VERSION
!endif
!ifndef APP_VERSION
  !define APP_VERSION "unknown"
!endif

Var UpdateMode

; The installer's and the uninstaller's own icon is the app's (F232, V3.17):
; until then NSIS's generic one, beside a program carrying PyInstaller's snake.
; Made by scripts/packaging/make_app_icon.py.
!define MUI_ICON "..\..\assets\icon\site_and_pattern.ico"
!define MUI_UNICON "..\..\assets\icon\site_and_pattern.ico"

; MUI Settings
!define MUI_PAGE_CUSTOMFUNCTION_PRE SkipInUpdateMode
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_PAGE_CUSTOMFUNCTION_PRE SkipInUpdateMode
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION OpenAppAsUser
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${GetParameters} $R0
  ClearErrors
  ${GetOptions} $R0 "/UPDATE" $R1
  ${IfNot} ${Errors}
    StrCpy $UpdateMode 1
  ${EndIf}
FunctionEnd

Function SkipInUpdateMode
  ${If} $UpdateMode == 1
    Abort
  ${EndIf}
FunctionEnd

; $0 = 1 when nothing holds the installed program, 0 while something does.
; A running program cannot be opened for writing, which is exactly what the
; File command needs, so ask that directly: no process list to parse in the
; machine's language, and no plugin to ship.
!macro _APP_FILE_IS_FREE FILE
  ${If} $0 == 1
  ${AndIf} ${FileExists} "${FILE}"
    ClearErrors
    FileOpen $1 "${FILE}" a
    ${If} ${Errors}
      StrCpy $0 0
    ${Else}
      FileClose $1
    ${EndIf}
  ${EndIf}
!macroend

!macro DEFINE_APP_IS_CLOSED PREFIX
Function ${PREFIX}AppIsClosed
  StrCpy $0 1
  !insertmacro _APP_FILE_IS_FREE "$INSTDIR\${APP_EXE}"
  !insertmacro _APP_FILE_IS_FREE "$INSTDIR\${WEB_ENGINE_EXE}"
FunctionEnd
!macroend
!insertmacro DEFINE_APP_IS_CLOSED ""
!insertmacro DEFINE_APP_IS_CLOSED "un."

; Nothing is copied until the program's files are free. In update mode the
; app is closing itself as this starts, so give it a minute; run by hand, ask
; at once. Cancel leaves the installed copy exactly as it was.
Function WaitForAppToClose
  StrCpy $2 0
  ${Do}
    Call AppIsClosed
    ${If} $0 == 1
      ${Break}
    ${EndIf}
    ${If} $UpdateMode == 1
    ${AndIf} $2 < ${WAIT_CHECKS}
      ${If} $2 == 0
        DetailPrint "Waiting for Site & Pattern to close..."
      ${EndIf}
      IntOp $2 $2 + 1
      Sleep 500
      ${Continue}
    ${EndIf}
    MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "${STILL_OPEN}" /SD IDCANCEL IDRETRY retry
    Quit
    retry:
    StrCpy $2 0
  ${Loop}
FunctionEnd

; Open Site & Pattern as the person who ran the installer, not as
; administrator. This installer runs elevated, and a program it started with
; Exec would be too, reading another account's data folder whenever someone
; else's password answered the Windows prompt. Explorer is already running as
; that person and opens the program the way a double-click does.
Function OpenAppAsUser
  Exec '"$WINDIR\explorer.exe" "$INSTDIR\${APP_EXE}"'
FunctionEnd

Function .onInstSuccess
  ${If} $UpdateMode == 1
    Call OpenAppAsUser
  ${EndIf}
FunctionEnd

; Installer sections
Section "Site & Pattern"
  Call WaitForAppToClose

  ; Replace the program rather than layer the new one over the old: a module
  ; the new version no longer ships must not stay importable. Only now, with
  ; nothing holding the files, and only where Site & Pattern is installed (a
  ; folder typed on the folder page could hold another program's _internal).
  ; None of it is the person's own: designs and the plant database live in
  ; their data folder, which is never touched here.
  ${If} ${FileExists} "$INSTDIR\${APP_EXE}"
    RMDir /r "$INSTDIR\_internal"
  ${EndIf}
  SetOutPath "$INSTDIR"
  File /r "..\..\dist\SiteAndPattern\*.*"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "${REG_KEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayName" "Site & Pattern"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\${APP_EXE}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair" 1

  ; Desktop shortcut. An update leaves the desktop as the person left it: one
  ; they deleted does not come back with every version.
  ${If} $UpdateMode != 1
  ${OrIf} ${FileExists} "$DESKTOP\Site & Pattern.lnk"
    CreateShortCut "$DESKTOP\Site & Pattern.lnk" "$INSTDIR\${APP_EXE}"
  ${EndIf}

  ; Create start menu shortcut
  CreateDirectory "$SMPROGRAMS\Site & Pattern"
  CreateShortCut "$SMPROGRAMS\Site & Pattern\Site & Pattern.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortCut "$SMPROGRAMS\Site & Pattern\Uninstall.lnk" "$INSTDIR\Uninstall.exe"

  ; Windows keeps icons in a cache by file, and can go on drawing a replaced
  ; program's old icon on its shortcuts until the next sign-in. Tell the shell
  ; the icons changed (SHCNE_ASSOCCHANGED), as installers that change one do.
  System::Call 'shell32::SHChangeNotify(i 0x08000000, i 0, p 0, p 0)'
SectionEnd

Function un.onInit
  ${Do}
    Call un.AppIsClosed
    ${If} $0 == 1
      ${Break}
    ${EndIf}
    MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "${STILL_OPEN}" /SD IDCANCEL IDRETRY retry
    Abort
    retry:
  ${Loop}
FunctionEnd

; Remove only what the installer put there. The uninstaller this replaced
; (never actually written until V3.15) did RMDir /r "$INSTDIR": a folder typed
; on the folder page, such as C:\Tools, would have gone with everything in it.
; The person's designs and database are in their data folder and stay.
Section "Uninstall"
  Delete "$INSTDIR\${APP_EXE}"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  RMDir /r "$SMPROGRAMS\Site & Pattern"
  Delete "$DESKTOP\Site & Pattern.lnk"
  DeleteRegKey HKLM "${UNINSTALL_KEY}"
  DeleteRegKey HKLM "${REG_KEY}"
SectionEnd
