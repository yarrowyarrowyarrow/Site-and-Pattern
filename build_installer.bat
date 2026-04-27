@echo off
setlocal enabledelayedexpansion

echo === PermaDesign Installer Builder ===
echo.

REM Clean previous builds
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Activate virtual environment if it exists
if exist venv (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Install build dependencies
echo Installing build dependencies...
pip install -q pyinstaller

REM Build with PyInstaller
echo Building application bundle with PyInstaller...
pyinstaller permadesign.spec --clean

REM Create Windows installer using NSIS (if available)
if exist "C:\Program Files (x86)\NSIS\makensis.exe" (
    echo Creating Windows installer with NSIS...
    if not exist build_nsis mkdir build_nsis

    REM Copy the dist folder to create the installer package
    echo Creating installer package...
    "C:\Program Files (x86)\NSIS\makensis.exe" /V4 installer.nsi

    if !ERRORLEVEL! equ 0 (
        echo ✓ Created PermaDesign-Installer.exe
    ) else (
        echo NSIS build failed. Creating zip archive instead...
        cd dist
        powershell -command "Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::CreateFromDirectory('PermaDesign', '..\PermaDesign-Windows.zip')"
        cd ..
        echo ✓ Created PermaDesign-Windows.zip
    )
) else (
    echo NSIS not found. Creating zip archive...
    cd dist
    powershell -command "Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::CreateFromDirectory('PermaDesign', '..\PermaDesign-Windows.zip')"
    cd ..
    echo ✓ Created PermaDesign-Windows.zip
)

echo.
echo === Build Complete ===
echo.
echo Installer location: %CD%\dist\
echo.
echo To run the application:
echo   dist\PermaDesign\PermaDesign.exe
echo.
pause
