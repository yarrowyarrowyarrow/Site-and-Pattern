@echo off
REM PermaDesign Windows build script
REM Run from the project root in a terminal. Produces dist\PermaDesign\PermaDesign.exe

echo Installing / updating build dependencies...
python -m pip install --upgrade pip
python -m pip install PyQt6>=6.6.0 "PyQt6-WebEngine>=6.6.0" pyinstaller

echo.
echo Building PermaDesign...
python -m PyInstaller PermaDesign.spec --clean --noconfirm

echo.
if exist "dist\PermaDesign\PermaDesign.exe" (
    echo BUILD SUCCEEDED
    echo Output: dist\PermaDesign\PermaDesign.exe
    echo.
    echo To distribute: zip the entire dist\PermaDesign\ folder.
    echo Users unzip it and double-click PermaDesign.exe — no Python required.
) else (
    echo BUILD FAILED — check the output above for errors.
    exit /b 1
)
