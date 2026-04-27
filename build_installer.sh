#!/bin/bash

set -e

echo "=== PermaDesign Installer Builder ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Clean previous builds
echo -e "${YELLOW}Cleaning previous builds...${NC}"
rm -rf build/ dist/ *.egg-info

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Install build dependencies
echo -e "${YELLOW}Installing build dependencies...${NC}"
pip install -q pyinstaller

# Build with PyInstaller
echo -e "${YELLOW}Building application bundle with PyInstaller...${NC}"
pyinstaller permadesign.spec --clean

# Create platform-specific installer
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS: Create DMG
    echo -e "${YELLOW}Creating macOS DMG installer...${NC}"
    mkdir -p dist/PermaDesign
    cp -r dist/PermaDesign/* dist/PermaDesign/ 2>/dev/null || true
    hdiutil create -volname "PermaDesign" -srcfolder dist/PermaDesign -ov -format UDZO dist/PermaDesign.dmg
    echo -e "${GREEN}✓ Created dist/PermaDesign.dmg${NC}"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux: Create AppImage (requires appimagetool)
    if command -v appimagetool &> /dev/null; then
        echo -e "${YELLOW}Creating Linux AppImage installer...${NC}"
        # This requires setting up an AppDir structure
        # For now, just zip the directory
        cd dist && zip -r -q ../PermaDesign-Linux.zip PermaDesign/ && cd ..
        echo -e "${GREEN}✓ Created PermaDesign-Linux.zip${NC}"
    else
        echo -e "${YELLOW}appimagetool not found. Creating zip archive instead...${NC}"
        cd dist && zip -r -q ../PermaDesign-Linux.zip PermaDesign/ && cd ..
        echo -e "${GREEN}✓ Created PermaDesign-Linux.zip${NC}"
    fi
else
    echo -e "${YELLOW}Unknown OS. Skipping platform-specific installer.${NC}"
fi

echo ""
echo -e "${GREEN}=== Build Complete ===${NC}"
echo ""
echo "Installer location: $(pwd)/dist/"
echo ""
echo "To run the application:"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "  ./dist/PermaDesign/PermaDesign.app/Contents/MacOS/PermaDesign"
else
    echo "  ./dist/PermaDesign/PermaDesign"
fi
