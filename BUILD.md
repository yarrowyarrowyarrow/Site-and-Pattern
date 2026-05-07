# PermaDesign Build & Deployment Guide

This document explains how to run PermaDesign locally and create a 1-click installer.

## Quick Start: Run Locally

### Prerequisites
- Python 3.9 or later
- Git (to clone the repository)

### Setup (One-time)

```bash
# Clone or navigate to the repository
cd /home/user/PermaDesign

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

The PermaDesign window should open. Create a new project to test functionality.

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
cd C:\path\to\PermaDesign
build_installer.bat
```

The script will:
1. Clean old builds
2. Run PyInstaller to create the executable
3. Create an NSIS installer (if installed) or a ZIP file
4. Output location: `dist\` folder

**Output files:**
- `PermaDesign-Installer.exe` (NSIS installer, ~200-300 MB)
- OR `PermaDesign-Windows.zip` (if NSIS not installed, ~250 MB)

#### Option B: Install NSIS for true 1-click installer

Download and install NSIS 3.x from: https://nsis.sourceforge.io/

Then run the build script (same as Option A).

#### Option C: Manual PyInstaller build

```cmd
venv\Scripts\activate.bat
pip install pyinstaller
pyinstaller permadesign.spec --clean
```

The executable will be in `dist\PermaDesign\PermaDesign.exe`.

### macOS: Create App Bundle & DMG

```bash
source venv/bin/activate
bash build_installer.sh
```

**Output:**
- `dist/PermaDesign.dmg` — Drag-and-drop installer (~200-300 MB)

### Linux: Create Executable & Archive

```bash
source venv/bin/activate
bash build_installer.sh
```

**Output:**
- `dist/PermaDesign/` — Executable directory
- `PermaDesign-Linux.zip` — Archive for distribution

Run via: `./dist/PermaDesign/PermaDesign`

---

## Distribution & Sharing

### For Users

1. **Windows**: Send `PermaDesign-Installer.exe` — they double-click to install
2. **macOS**: Send `PermaDesign.dmg` — they drag PermaDesign.app to Applications
3. **Linux**: Send `PermaDesign-Linux.zip` — they extract and run the binary

### File Sizes (Typical)

- **Installer/DMG/ZIP**: 200–300 MB (includes all dependencies)
- **Installed size**: 400–600 MB (PyQt6 WebEngine is large)

### Code Signing (Optional, Advanced)

To avoid security warnings on macOS/Windows:

**macOS:**
```bash
codesign -s - dist/PermaDesign/PermaDesign.app/Contents/MacOS/PermaDesign
```

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
   - **Windows**: `"C:\Program Files\PermaDesign\PermaDesign.exe"`
   - **macOS**: `./dist/PermaDesign/PermaDesign.app/Contents/MacOS/PermaDesign`
   - **Linux**: `./dist/PermaDesign/PermaDesign`
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

Currently the spec creates a folder (`PermaDesign/`). To make a single `.exe`:

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
| **Windows** | `build_installer.bat` | `PermaDesign-Installer.exe` (or ZIP) | Double-click, 1-click install |
| **macOS** | `bash build_installer.sh` | `PermaDesign.dmg` | Drag to Applications |
| **Linux** | `bash build_installer.sh` | `PermaDesign-Linux.zip` | Extract & run binary |

All builds are fully self-contained with zero external dependencies after install.
