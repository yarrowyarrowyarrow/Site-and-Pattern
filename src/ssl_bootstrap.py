"""
src/ssl_bootstrap.py — point Python's SSL stack at a usable CA bundle.

On macOS the OpenSSL linked into CPython ships with no root certificates:
python.org installers expect the user to run "Install Certificates.command"
(which nobody does), and PyInstaller-frozen builds have no system bundle at
all. Every https ``urlopen()`` then fails with CERTIFICATE_VERIFY_FAILED —
silently, because the fetch helpers degrade to their offline fallbacks, so
plant photos, Open-Meteo elevation, Edmonton contours and Overpass imports
all just "don't work". (QtWebEngine is unaffected: Chromium carries its own
root store, which is why the base map keeps working while every
Python-side fetch fails.)

:func:`ensure_ca_bundle` makes the default SSL context verifiable
everywhere: if the interpreter's default verify paths don't exist on disk
and the process hasn't already been pointed at a bundle via
``SSL_CERT_FILE``/``SSL_CERT_DIR``, it points ``SSL_CERT_FILE`` at
certifi's bundled PEM. Linux distro Pythons (whose system paths do exist)
are left untouched. It must run before the process's first https request;
OpenSSL re-reads the env var whenever a default context loads its certs,
so calling it once at startup is sufficient.
"""

from __future__ import annotations

import os
import ssl
from typing import Optional


def _default_verify_paths_exist() -> bool:
    """True when the interpreter's compiled-in CA locations actually exist.

    ``ssl.get_default_verify_paths()`` already nulls out paths whose file or
    directory is missing; the extra existence checks guard against an empty
    cert directory, which some minimal installs ship.
    """
    paths = ssl.get_default_verify_paths()
    if paths.cafile and os.path.isfile(paths.cafile):
        return True
    if paths.capath and os.path.isdir(paths.capath) and os.listdir(paths.capath):
        return True
    return False


def ensure_ca_bundle() -> Optional[str]:
    """Make https verification work; idempotent and safe on every platform.

    Returns the CA file now in effect, or ``None`` when nothing needed
    doing (working system bundle, caller already set the env vars, or
    certifi unavailable — the last keeps pre-fix behaviour rather than
    making things worse).
    """
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return os.environ.get("SSL_CERT_FILE")   # user/process already chose
    if _default_verify_paths_exist():
        return None                              # system bundle works
    try:
        import certifi
    except ImportError:
        return None
    cafile = certifi.where()
    if not (cafile and os.path.isfile(cafile)):
        return None
    os.environ["SSL_CERT_FILE"] = cafile
    return cafile
