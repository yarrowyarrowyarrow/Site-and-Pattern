# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Site & Pattern (one-directory bundled mode)
# Build with: pyinstaller scripts/packaging/permadesign.spec  (from the repo root)
# Display name is "Site & Pattern"; the artifact base name is the script-safe
# "SiteAndPattern" (no spaces/ampersand) so the build scripts and NSIS paths
# stay quoting-safe. Shortcuts/Start-Menu/.app show the display name.

import fnmatch
import os
import sys

block_cipher = None

# This spec lives in scripts/packaging/, but the build scripts always invoke
# PyInstaller with the repo root as the working directory (they cd there first).
# Anchor every source path to that working dir so bundling is unambiguous
# regardless of where the spec file sits.
_ROOT = os.getcwd()

# What the source tree holds and the installed app never reads (V3.22, RM-7):
# the raw downloads the seed scripts derive the catalogue from (about 32 MB),
# and the developer pages the tests and the tuning benches open from the
# source tree. Matched against paths relative to the repo root, with '/'.
_NOT_SHIPPED = (
    'data/fetched/*',
    'html/*_probe.html',
    'html/inspect_probe_data.json',
    'html/tune_*.html',
    'html/sprite_gallery*',
)


def _tree(top):
    """Every file under ``top`` but the ones ``_NOT_SHIPPED`` names, as
    ``(source, destination folder)`` pairs."""
    out = []
    for folder, subfolders, files in os.walk(os.path.join(_ROOT, top)):
        subfolders[:] = sorted(d for d in subfolders if d != '__pycache__')
        for name in sorted(files):
            source = os.path.join(folder, name)
            rel = os.path.relpath(source, _ROOT).replace(os.sep, '/')
            if not any(fnmatch.fnmatch(rel, p) for p in _NOT_SHIPPED):
                out.append((source, os.path.dirname(rel)))
    return out


# Runtime data files, preserving their relative layout under the bundle root.
_datas = _tree('data') + _tree('html') + [
    (os.path.join(_ROOT, 'src', 'db', 'schema.sql'), 'src/db'),
    # The window icon at every size (src/app_icon.py).
    (os.path.join(_ROOT, 'assets', 'icon', 'app_*.png'), 'assets/icon'),
    # The licence's text (V3.18, FN-1): the GPL v3 asks that everyone who
    # receives the program receives the licence with it, and Help › About
    # points to this file.
    (os.path.join(_ROOT, 'LICENSE'), '.'),
    # The licences of what ships with it (V3.31, FN-2), written by
    # scripts/write_third_party_notices.py.
    (os.path.join(_ROOT, 'THIRD_PARTY_NOTICES.txt'), '.'),
]

# The app's icon (F232, V3.17), made by scripts/packaging/make_app_icon.py.
# Left at None, PyInstaller puts its own on the program: a snake on a floppy
# disk, the icon of a great deal of malware.
_ICON_WINDOWS = os.path.join(_ROOT, 'assets', 'icon', 'site_and_pattern.ico')
_ICON_MAC = os.path.join(_ROOT, 'assets', 'icon', 'site_and_pattern.icns')
# version.txt is written by build_installer.sh / .bat (or the release
# workflow) just before this spec runs; it lets the frozen app know which
# V<major>.<minor> it is for the in-app updater (src/app_version.py). It is
# absent in a plain source checkout, so only bundle it when present.
if os.path.exists(os.path.join(_ROOT, 'version.txt')):
    _datas.append((os.path.join(_ROOT, 'version.txt'), '.'))
# build-versions.txt (V3.31, FN-12): what the build scripts installed, so an
# installer says which libraries it carries. Written beside version.txt.
if os.path.exists(os.path.join(_ROOT, 'build-versions.txt')):
    _datas.append((os.path.join(_ROOT, 'build-versions.txt'), '.'))

a = Analysis(
    [os.path.join(_ROOT, 'main.py')],
    pathex=[_ROOT],
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
    icon=_ICON_WINDOWS,
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
        icon=_ICON_MAC,
        bundle_identifier='com.siteandpattern.app',
        info_plist={
            'CFBundleName': 'Site & Pattern',
            'CFBundleDisplayName': 'Site & Pattern',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '11.0',
        },
    )
