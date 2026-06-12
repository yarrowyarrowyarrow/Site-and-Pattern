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
    # macOS: package the .app bundle into a drag-to-install DMG
    APP="dist/PermaDesign.app"
    if [ ! -d "$APP" ]; then
        echo "ERROR: $APP not found — the darwin BUNDLE step in permadesign.spec did not run." >&2
        exit 1
    fi

    # Re-apply an ad-hoc signature over the whole bundle. PyInstaller signs
    # ad-hoc by default, but a final deep re-sign prevents Gatekeeper
    # "app is damaged" errors on recipients' Macs.
    echo -e "${YELLOW}Ad-hoc signing the app bundle...${NC}"
    codesign --force --deep -s - "$APP"

    echo -e "${YELLOW}Creating macOS DMG installer...${NC}"
    STAGING="dist/dmg-staging"
    rm -rf "$STAGING"
    mkdir -p "$STAGING"
    cp -R "$APP" "$STAGING/"
    ln -s /Applications "$STAGING/Applications"
    cat > "$STAGING/READ ME FIRST.txt" <<'EOF'
Installing PermaDesign
======================

1. Drag the PermaDesign icon onto the Applications folder in this window.

2. The FIRST time you open it, macOS will warn you because the app is not
   notarized by Apple. This is a one-time step:

   * macOS 11-14 (Big Sur through Sonoma):
     In Applications, right-click (or Ctrl-click) PermaDesign, choose
     "Open", then click "Open" in the dialog.

   * macOS 15 (Sequoia) or newer:
     Double-click PermaDesign once (it will be blocked), then open
     System Settings > Privacy & Security, scroll down, and click
     "Open Anyway" next to PermaDesign.

3. Apple Silicon (M1/M2/M3/M4) Macs: if macOS offers to install Rosetta
   on first launch, click Install (one time only).

After the first launch, PermaDesign opens normally like any other app.
EOF
    hdiutil create -volname "PermaDesign" -srcfolder "$STAGING" -ov -format UDZO dist/PermaDesign.dmg
    rm -rf "$STAGING"
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
    echo "  open dist/PermaDesign.app"
    echo ""
    echo "To share with other Macs (macOS 11 Big Sur or newer):"
    echo "  send dist/PermaDesign.dmg"
else
    echo "  ./dist/PermaDesign/PermaDesign"
fi
