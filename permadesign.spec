# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Site & Pattern (one-directory bundled mode)
# Build with: pyinstaller permadesign.spec
# Display name is "Site & Pattern"; the artifact base name is the script-safe
# "SiteAndPattern" (no spaces/ampersand) so the build scripts and NSIS paths
# stay quoting-safe. Shortcuts/Start-Menu/.app show the display name.

import os
import sys

block_cipher = None

# Runtime data files, preserving their relative layout under the bundle root.
_datas = [
    ('data', 'data'),
    ('html', 'html'),
    ('src/db/schema.sql', 'src/db'),
]
# version.txt is written by build_installer.sh / .bat (or the release
# workflow) just before this spec runs; it lets the frozen app know which
# V<major>.<minor> it is for the in-app updater (src/app_version.py). It is
# absent in a plain source checkout, so only bundle it when present.
if os.path.exists('version.txt'):
    _datas.append(('version.txt', '.'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=_datas,
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.sip',
        'sqlite3',
        # CA bundle for https fetches in frozen builds (the bundled
        # Python has no system certificates; see src/ssl_bootstrap.py).
        # PyInstaller's certifi hook packs cacert.pem alongside it.
        'certifi',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
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
    name='SiteAndPattern',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SiteAndPattern',
)

if sys.platform == 'darwin':
    # Wrap the one-directory build in a proper .app bundle so macOS users
    # get a normal double-clickable application. LSMinimumSystemVersion
    # matches the Qt 6.7 cap in requirements.txt (Big Sur 11 onwards).
    app = BUNDLE(
        coll,
        name='SiteAndPattern.app',
        icon=None,
        bundle_identifier='com.siteandpattern.app',
        info_plist={
            'CFBundleName': 'Site & Pattern',
            'CFBundleDisplayName': 'Site & Pattern',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '11.0',
        },
    )
