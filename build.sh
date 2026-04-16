#!/usr/bin/env bash
# PermaDesign Linux build script
# Run from the project root. Produces dist/PermaDesign/PermaDesign

set -e

echo "Installing / updating build dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install "PyQt6>=6.6.0" "PyQt6-WebEngine>=6.6.0" pyinstaller

echo ""
echo "Building PermaDesign..."
python3 -m PyInstaller PermaDesign.spec --clean --noconfirm

echo ""
if [ -f "dist/PermaDesign/PermaDesign" ]; then
    echo "BUILD SUCCEEDED"
    echo "Output: dist/PermaDesign/PermaDesign"
    echo ""
    echo "To distribute: tar or zip the dist/PermaDesign/ folder."
    echo "Users extract it and double-click PermaDesign (or run ./PermaDesign)."
else
    echo "BUILD FAILED — check the output above for errors."
    exit 1
fi
