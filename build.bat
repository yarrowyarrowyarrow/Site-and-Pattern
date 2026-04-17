@echo off
REM PermaDesign Windows build script
REM Produces dist\PermaDesign-Setup.exe (requires Inno Setup 6)
REM Download Inno Setup 6 free from: https://jrsoftware.org/isdl.php

echo Installing / updating build dependencies...
python -m pip install --upgrade pip
python -m pip install "PyQt6>=6.6.0" "PyQt6-WebEngine>=6.6.0" pyinstaller

echo.
echo Building PermaDesign (PyInstaller)...
python -m PyInstaller PermaDesign.spec --clean --noconfirm

echo.
if not exist "dist\PermaDesign\PermaDesign.exe" (
    echo BUILD FAILED - PyInstaller did not produce an executable.
    echo Check the output above for errors.
    exit /b 1
)
echo PyInstaller build succeeded.

REM ── Find Inno Setup ────────────────────────────────────────────────────────
set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if "%ISCC%"=="" (
    echo.
    echo NOTE: Inno Setup 6 not found - installer step skipped.
    echo To produce a single PermaDesign-Setup.exe installer:
    echo   1. Download Inno Setup 6 from https://jrsoftware.org/isdl.php
    echo   2. Install it, then re-run this script.
    echo.
    echo You can still share the dist\PermaDesign\ folder - zip it and
    echo friends double-click PermaDesign.exe inside.
    goto :done
)

echo.
echo Building installer (Inno Setup)...
"%ISCC%" PermaDesign.iss

if exist "dist\PermaDesign-Setup.exe" (
    echo.
    echo ============================================================
    echo  INSTALLER READY: dist\PermaDesign-Setup.exe
    echo  Share this single file - friends double-click to install.
    echo ============================================================
) else (
    echo Inno Setup step failed - check output above.
    exit /b 1
)

:done
