@echo off
setlocal enabledelayedexpansion

echo === Site ^& Pattern Installer Builder ===
echo.

REM Kill any lingering app processes that hold file locks on the old build.
REM Without this, rmdir fails silently and PyInstaller produces a corrupt bundle.
echo Stopping any running Site ^& Pattern processes...
taskkill /F /IM SiteAndPattern.exe >nul 2>&1
taskkill /F /IM QtWebEngineProcess.exe >nul 2>&1

REM Clean previous builds, and FAIL HARD if anything is locked.
echo Cleaning previous builds...
if exist build (
    rmdir /s /q build
    if exist build (
        echo ERROR: could not delete build\ - a file is locked.
        echo Close any open Site ^& Pattern windows / Explorer windows in that folder and retry.
        exit /b 1
    )
)
if exist dist (
    rmdir /s /q dist
    if exist dist (
        echo ERROR: could not delete dist\ - a file is locked.
        echo Close any open Site ^& Pattern windows / Explorer windows in that folder and retry.
        exit /b 1
    )
)
if exist SiteAndPattern-Windows.zip del /q SiteAndPattern-Windows.zip

REM Activate virtual environment if it exists
if exist venv (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Install runtime + build dependencies. requirements.txt must be installed
REM first so PyInstaller can actually find PyQt6 et al. to bundle — otherwise
REM it silently produces a broken app that crashes on launch.
echo Installing dependencies...
pip install -q -r requirements.txt
if !ERRORLEVEL! neq 0 (
    echo ERROR: failed to install requirements.txt. Aborting.
    exit /b 1
)
pip install -q pyinstaller

REM Build with PyInstaller — bail if it fails so we don't ship a broken bundle.
echo Building application bundle with PyInstaller...
pyinstaller permadesign.spec --clean
if !ERRORLEVEL! neq 0 (
    echo ERROR: PyInstaller build failed. Aborting.
    exit /b 1
)
if not exist dist\SiteAndPattern\SiteAndPattern.exe (
    echo ERROR: dist\SiteAndPattern\SiteAndPattern.exe was not produced. Aborting.
    exit /b 1
)

REM Create Windows installer using NSIS (if available)
if exist "C:\Program Files (x86)\NSIS\makensis.exe" (
    echo Creating Windows installer with NSIS...
    if not exist build_nsis mkdir build_nsis

    REM Copy the dist folder to create the installer package
    echo Creating installer package...
    "C:\Program Files (x86)\NSIS\makensis.exe" /V4 installer.nsi

    if !ERRORLEVEL! equ 0 (
        echo Created SiteAndPattern-Installer.exe
    ) else (
        echo NSIS build failed. Creating zip archive instead...
        cd dist
        powershell -command "Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::CreateFromDirectory('SiteAndPattern', '..\SiteAndPattern-Windows.zip')"
        cd ..
        echo Created SiteAndPattern-Windows.zip
    )
) else (
    echo NSIS not found. Creating zip archive...
    cd dist
    powershell -command "Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::CreateFromDirectory('SiteAndPattern', '..\SiteAndPattern-Windows.zip')"
    cd ..
    echo Created SiteAndPattern-Windows.zip
)

echo.
echo === Build Complete ===
echo.
echo Installer location: %CD%\dist\
echo.
echo To run the application:
echo   dist\SiteAndPattern\SiteAndPattern.exe
echo.
pause
