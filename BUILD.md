# Site & Pattern Build & Deployment Guide

This document explains how to run Site & Pattern locally and create a 1-click installer.

## Quick Start: Run Locally

### Prerequisites
- Python 3.9 or later
- Git (to clone the repository)

### Setup (One-time)

```bash
# Clone or navigate to the repository
cd /home/user/Site & Pattern

# Create a virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate              # Linux/macOS
# OR
venv\Scripts\activate.bat             # Windows (Command Prompt)
# OR
venv\Scripts\Activate.ps1             # Windows (PowerShell)

# Install dependencies
pip install -r requirements.txt
```

### Run the Application

```bash
python3 main.py
```

The Site & Pattern window should open. Create a new project to test functionality.

---

## Building an Installer

### Prerequisites for Building

1. **All local setup steps above**
2. **PyInstaller**: Installed automatically when you run the build script
3. **Platform-specific requirements**:
   - **Windows**: NSIS 3.x (optional; ZIP fallback is automatic)
   - **macOS**: Built-in tools (no extra dependencies)
   - **Linux**: ZIP archive (or `appimagetool` for AppImage format)

### Windows: 1-Click Installer

#### Option A: Using build script (Recommended)

```cmd
cd C:\path\to\Site & Pattern
build_installer.bat
```

The script will:
1. Clean old builds
2. Run PyInstaller to create the executable
3. Create an NSIS installer (if installed) or a ZIP file
4. Output location: `dist\` folder

**Output files:**
- `SiteAndPattern-Installer.exe` (NSIS installer, ~200-300 MB)
- OR `SiteAndPattern-Windows.zip` (if NSIS not installed, ~250 MB)

#### Option B: Install NSIS for true 1-click installer

Download and install NSIS 3.x from: https://nsis.sourceforge.io/

Then run the build script (same as Option A).

#### Option C: Manual PyInstaller build

```cmd
venv\Scripts\activate.bat
pip install pyinstaller
pyinstaller permadesign.spec --clean
```

The executable will be in `dist\SiteAndPattern\SiteAndPattern.exe`.

### macOS: Create App Bundle & DMG

```bash
git clone https://github.com/yarrowyarrowyarrow/PermaDesign.git
cd PermaDesign
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
bash build_installer.sh
```

**Output:**
- `dist/SiteAndPattern.app` — the application bundle (run it with `open dist/SiteAndPattern.app`)
- `dist/SiteAndPattern.dmg` — drag-and-drop installer for sharing (~200-300 MB)

The DMG contains the app, an Applications shortcut for drag-to-install, and
a `READ ME FIRST.txt` explaining the one-time unsigned-app launch step.

**Big Sur (macOS 11) compatibility notes:**
- `requirements.txt` pins Qt to the 6.7 series on macOS — Qt 6.8+ requires
  macOS 12 and would silently break Big Sur support. Don't override the pin.
- Build on the **oldest macOS you intend to support** (e.g. a Big Sur
  machine). The resulting app runs on that version and everything newer.
- An Intel-built app also runs on Apple Silicon Macs via Rosetta (macOS
  offers a one-click Rosetta install on first launch if needed).

**Unsigned-app warning (no Apple Developer account):**
The build script applies an ad-hoc code signature, which prevents
"app is damaged" errors, but recipients still see a one-time Gatekeeper
warning on first launch:
- macOS 11–14: right-click the app → Open → Open (once).
- macOS 15+: double-click once (blocked), then System Settings →
  Privacy & Security → "Open Anyway".

Removing that warning entirely requires an Apple Developer account
(US$99/yr): set `codesign_identity` (a "Developer ID Application"
certificate) and `entitlements_file` in `permadesign.spec`, then notarize
the DMG with `xcrun notarytool submit` and staple the ticket.

### Linux: Create Executable & Archive

```bash
source venv/bin/activate
bash build_installer.sh
```

**Output:**
- `dist/SiteAndPattern/` — Executable directory
- `SiteAndPattern-Linux.zip` — Archive for distribution

Run via: `./dist/SiteAndPattern/SiteAndPattern`

---

## Distribution & Sharing

### For Users

1. **Windows**: Send `SiteAndPattern-Installer.exe` — they double-click to install
2. **macOS**: Send `SiteAndPattern.dmg` — they drag SiteAndPattern.app to Applications
   (the `READ ME FIRST.txt` inside the DMG covers the one-time first-launch step)
3. **Linux**: Send `SiteAndPattern-Linux.zip` — they extract and run the binary

### File Sizes (Typical)

- **Installer/DMG/ZIP**: 200–300 MB (includes all dependencies)
- **Installed size**: 400–600 MB (PyQt6 WebEngine is large)

### Code Signing (Optional, Advanced)

To avoid security warnings on macOS/Windows:

**macOS:** `build_installer.sh` already applies an ad-hoc signature
(`codesign --force --deep -s - dist/SiteAndPattern.app`). Fully removing the
first-launch Gatekeeper warning requires an Apple Developer ID certificate
plus notarization — see the macOS build section above.

**Windows:** Requires a code-signing certificate (paid or self-signed).

---

## Troubleshooting

### "PyInstaller not found"
```bash
pip install pyinstaller
```

### "NSIS makensis not found" (Windows)
The script automatically falls back to creating a ZIP file. To enable true 1-click installer:
1. Download NSIS from https://nsis.sourceforge.io/
2. Install to `C:\Program Files (x86)\NSIS\`
3. Rebuild

### Network features don't work (no plant photos / elevation / OSM import)
Python needs root certificates to verify https connections. macOS Pythons
and frozen builds ship none, so every web fetch fails silently while the
map itself (Chromium, own cert store) keeps working. Site & Pattern wires up
`certifi`'s CA bundle automatically at startup (`src/ssl_bootstrap.py`);
if network features fail on a source install, update dependencies so
certifi is present: `pip install -r requirements.txt`, then rebuild if
packaging.

### "Missing module" error
Add the module to `permadesign.spec` under `hiddenimports`:

```python
hiddenimports=[
    'PyQt6',
    'your_missing_module',  # Add here
    ...
]
```

### Application won't start after install
The installer includes all dependencies. If it fails to start:
1. Run from command line to see error messages:
   - **Windows**: `"C:\Program Files\Site & Pattern\SiteAndPattern.exe"`
   - **macOS**: `dist/SiteAndPattern.app/Contents/MacOS/SiteAndPattern`
   - **Linux**: `./dist/SiteAndPattern/SiteAndPattern`
2. Check that `data/` and `html/` directories are included

---

## Advanced: Customization

### Change Icon

1. Create a `.png` or `.ico` file (256x256+ pixels)
2. Edit `permadesign.spec` and update the `exe` section:
```python
exe = EXE(
    ...
    icon='path/to/your/icon.ico',  # Add this line
)
```
3. Rebuild

### Bundle Additional Assets

Edit `permadesign.spec` under `datas`:
```python
datas=[
    ('data', 'data'),           # Already included
    ('html', 'html'),           # Already included
    ('path/to/extra', 'extra'), # Add custom assets
],
```

### One-File vs. One-Folder

Currently the spec creates a folder (`Site & Pattern/`). To make a single `.exe`:

Edit `permadesign.spec` — change the `EXE` section from `COLLECT()` to use `--onefile`:
```bash
pyinstaller permadesign.spec --onefile
```

**Trade-off**: Single file (~400 MB) but slower startup (~5-10 seconds). Not recommended for users unless disk space is critical.

---

## Continuous Build (CI/CD)

For automated builds on each commit, add GitHub Actions to `.github/workflows/build.yml`:

```yaml
name: Build Installers
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt pyinstaller
      - run: pyinstaller permadesign.spec --clean
      - uses: actions/upload-artifact@v2
        with:
          name: builds
          path: dist/
```

---

## Summary

| Platform | Build Command | Output | User Experience |
|----------|---|---|---|
| **Windows** | `build_installer.bat` | `SiteAndPattern-Installer.exe` (or ZIP) | Double-click, 1-click install |
| **macOS** | `bash build_installer.sh` | `SiteAndPattern.dmg` | Drag to Applications |
| **Linux** | `bash build_installer.sh` | `SiteAndPattern-Linux.zip` | Extract & run binary |

All builds are fully self-contained with zero external dependencies after install.
