#!/bin/bash

set -e

# Always operate from the repository root so every relative path (build/, dist/,
# version.txt, the spec) resolves the same regardless of how this is invoked —
# CI calls it as scripts/packaging/build_installer.sh.
cd "$(dirname "$0")/../.." || exit 1

echo "=== Site & Pattern Installer Builder ==="
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

# Bake the version into the bundle so the frozen app knows which
# V<major>.<minor> it is for the in-app updater (src/app_version.py). CI
# passes APP_BUILD_VERSION (the branch/tag); locally we read the git branch.
BUILD_VERSION="${APP_BUILD_VERSION:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")}"
echo "${BUILD_VERSION}" > version.txt
echo -e "${YELLOW}Baking version: ${BUILD_VERSION:-<unknown>}${NC}"

# Build with PyInstaller
echo -e "${YELLOW}Building application bundle with PyInstaller...${NC}"
pyinstaller scripts/packaging/permadesign.spec --clean

# Create platform-specific installer
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS: package the .app bundle into a drag-to-install DMG
    APP="dist/SiteAndPattern.app"
    if [ ! -d "$APP" ]; then
        echo "ERROR: $APP not found — the darwin BUNDLE step in permadesign.spec did not run." >&2
        exit 1
    fi

    # --- Ad-hoc code signing (inside-out) --------------------------------
    # A *valid* signature is what lets a recipient clear Gatekeeper with a
    # simple right-click -> Open. A broken/partial signature instead makes
    # macOS report the app as "damaged and can't be opened", which CANNOT be
    # cleared without Terminal — this is the failure mode where a re-downloaded
    # DMG refuses to launch. `codesign --deep` is deprecated and routinely
    # leaves nested Qt/WebEngine binaries unsealed, so we sign deepest-first
    # by hand and then verify the seal, failing the build loudly if it is not
    # valid (better a failed build than a "damaged" DMG on a friend's Mac).
    echo -e "${YELLOW}Clearing stray extended attributes...${NC}"
    xattr -cr "$APP"

    echo -e "${YELLOW}Ad-hoc signing nested binaries (deepest first)...${NC}"
    # 1. Plain Mach-O libraries (.dylib / .so)
    find "$APP" -type f \( -name "*.dylib" -o -name "*.so" \) \
        -exec codesign --force --timestamp=none -s - {} \;
    # 2. Embedded frameworks (codesign handles their internal layout)
    find "$APP" -type d -name "*.framework" \
        -exec codesign --force --timestamp=none -s - {} \;
    # 3. Embedded helper apps (e.g. QtWebEngineProcess.app)
    find "$APP/Contents" -type d -name "*.app" \
        -exec codesign --force --timestamp=none -s - {} \;
    # 4. Finally seal the outer bundle (this also signs the main executable)
    codesign --force --timestamp=none -s - "$APP"

    echo -e "${YELLOW}Verifying the signature seal...${NC}"
    if ! codesign --verify --deep --strict --verbose=2 "$APP"; then
        echo "ERROR: the ad-hoc signature did not verify. A DMG built from this" >&2
        echo "       bundle would be reported as 'damaged' on other Macs and" >&2
        echo "       could not be opened without Terminal. Aborting the build." >&2
        exit 1
    fi
    echo -e "${GREEN}✓ Signature verified (ad-hoc). Right-click -> Open will work.${NC}"

    echo -e "${YELLOW}Creating macOS DMG installer...${NC}"
    STAGING="dist/dmg-staging"
    rm -rf "$STAGING"
    mkdir -p "$STAGING"
    cp -R "$APP" "$STAGING/"
    ln -s /Applications "$STAGING/Applications"
    cat > "$STAGING/READ ME FIRST.txt" <<'EOF'
=====================================================
  Installing Site & Pattern  (please read — 2 minutes)
=====================================================

STEP 1 — Install the app
------------------------
Drag the "Site & Pattern" icon onto the Applications folder shown in
this window. That copies the app into your Applications. You can now
eject this disk (drag it to the Trash / Eject).


STEP 2 — Open it the FIRST time (one-time only)
-----------------------------------------------
This app is made by a small project and is not registered with Apple,
so the very first time you open it macOS shows a security warning. This
is normal and the app is safe. Just DOUBLE-CLICKING will NOT work the
first time — follow the matching steps below ONCE:

  >> If you are on macOS 11, 12, 13 or 14 (Big Sur / Monterey /
     Ventura / Sonoma):
       1. Open your Applications folder.
       2. RIGHT-CLICK (or hold Control and click) "Site & Pattern".
       3. Choose "Open" from the little menu.
       4. A box appears with an "Open" button — click it.

  >> If you are on macOS 15 (Sequoia) or newer, OR the steps above
     don't show an "Open" button:
       1. Double-click "Site & Pattern" once. It gets blocked — that's
          expected. Click "Done" / "Cancel".
       2. Open the Apple menu  >  System Settings  >  Privacy & Security.
       3. Scroll down to the Security section. You'll see a line that
          says "Site & Pattern was blocked..." with an
          "Open Anyway" button. Click it (enter your password if asked).
       4. Click "Open Anyway" again in the confirmation box.

  (Which macOS am I on? Apple menu > About This Mac.)


STEP 3 — That's it
------------------
After this one time, "Site & Pattern" opens normally like any other app
forever after — just double-click it.


Apple Silicon Macs (M1 / M2 / M3 / M4):
If macOS offers to install "Rosetta" on first launch, click Install
(one time only). Let it finish, then open the app again.

Trouble? It still says "damaged" or won't open:
Re-download the .dmg (a half-finished download can corrupt it), then
repeat Step 1 and Step 2.
EOF
    hdiutil create -volname "Site & Pattern" -srcfolder "$STAGING" -ov -format UDZO dist/SiteAndPattern.dmg
    rm -rf "$STAGING"
    echo -e "${GREEN}✓ Created dist/SiteAndPattern.dmg${NC}"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux: Create AppImage (requires appimagetool)
    if command -v appimagetool &> /dev/null; then
        echo -e "${YELLOW}Creating Linux AppImage installer...${NC}"
        # This requires setting up an AppDir structure
        # For now, just zip the directory
        cd dist && zip -r -q ../SiteAndPattern-Linux.zip SiteAndPattern/ && cd ..
        echo -e "${GREEN}✓ Created SiteAndPattern-Linux.zip${NC}"
    else
        echo -e "${YELLOW}appimagetool not found. Creating zip archive instead...${NC}"
        cd dist && zip -r -q ../SiteAndPattern-Linux.zip SiteAndPattern/ && cd ..
        echo -e "${GREEN}✓ Created SiteAndPattern-Linux.zip${NC}"
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
    echo "  open dist/SiteAndPattern.app"
    echo ""
    echo "To share with other Macs (macOS 11 Big Sur or newer):"
    echo "  send dist/SiteAndPattern.dmg"
else
    echo "  ./dist/SiteAndPattern/SiteAndPattern"
fi
