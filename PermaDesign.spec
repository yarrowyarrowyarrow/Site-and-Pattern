# -*- mode: python ; coding: utf-8 -*-
#
# PermaDesign PyInstaller spec
#
# Build:
#   Windows:  build.bat
#   Linux:    build.sh
#
# Output: dist/PermaDesign/PermaDesign(.exe)
#
# Notes on PyQt6-WebEngine:
#   WebEngine requires Chromium resources to be bundled. Using
#   collect_all('PyQt6') and collect_all('PyQt6.QtWebEngineWidgets')
#   ensures all Qt resources, translations, and the QtWebEngineProcess
#   helper binary are included.

from PyInstaller.utils.hooks import collect_all, collect_data_files
import os

block_cipher = None

# Collect ALL PyQt6 data/binaries (includes WebEngine resources + helper)
qt6_datas, qt6_binaries, qt6_hiddenimports = collect_all('PyQt6')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=qt6_binaries,
    datas=[
        # App resources
        ('html', 'html'),
        ('data/plants.json', 'data'),
        ('data/hardiness_zones.json', 'data'),
        ('src/db/schema.sql', os.path.join('src', 'db')),
        # PyQt6 resources
        *qt6_datas,
    ],
    hiddenimports=[
        'sqlite3',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebChannel',
        'PyQt6.QtPrintSupport',
        *qt6_hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PermaDesign',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # no terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',  # uncomment and add icon file to enable
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PermaDesign',
)
