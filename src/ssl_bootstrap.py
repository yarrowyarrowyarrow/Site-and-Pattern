"""
src/ssl_bootstrap.py — point Python's SSL stack at a usable CA bundle.

macOS OpenSSL-based Pythons cannot see the system Keychain, so https
verification depends on whatever PEM bundle happens to sit at OpenSSL's
compiled-in path: python.org builds ship none (the user is expected to run
"Install Certificates.command"), Homebrew builds point at a bundle that
may be stale or broken, and PyInstaller-frozen builds have nothing at all.
Every https ``urlopen()`` then fails with CERTIFICATE_VERIFY_FAILED —
silently, because the fetch helpers degrade to their offline fallbacks, so
plant photos, elevation, Edmonton contours, OSM import and address search
all just "don't work". (QtWebEngine is unaffected: Chromium carries its
own root store, which is why the base map keeps working regardless.)

:func:`ensure_ca_bundle` therefore prefers certifi's Mozilla bundle
**always on macOS** — a merely *present* bundle proved untrustworthy in
the wild (stale Homebrew cert.pem) — and elsewhere only when the default
SSL context genuinely loads zero CA certificates (checked functionally
via ``cert_store_stats``, not by path existence). Explicit
``SSL_CERT_FILE``/``SSL_CERT_DIR`` env vars always win. It must run
before the process's first https request; OpenSSL re-reads the env var
whenever a default context loads its certs, so calling it once at
startup is sufficient.
"""

from __future__ import annotations

import os
import ssl
import sys
from typing import Optional


def _context_has_ca_certs() -> bool:
    """Functionally check whether a default SSL context loads any CA certs.

    Path-existence checks are not enough: a cert file can exist and still
    be empty, a broken symlink, or stale. An empty store always means
    verification will fail; a non-empty one is trusted everywhere except
    macOS (see module docstring).
    """
    try:
        ctx = ssl.create_default_context()
        return ctx.cert_store_stats().get("x509_ca", 0) > 0
    except Exception:
        return False


def ensure_ca_bundle(verbose: bool = True) -> Optional[str]:
    """Make https verification work; idempotent and safe on every platform.

    Returns the CA file now in effect, or ``None`` when nothing needed
    doing or nothing could be done. With ``verbose`` (the default) the
    outcome is logged to stderr so a terminal session shows at a glance
    whether the bundle was wired up.
    """
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return os.environ.get("SSL_CERT_FILE")   # user/process already chose

    # On macOS never trust a merely-present OpenSSL bundle; elsewhere only
    # step in when the default context demonstrably has no CAs.
    if sys.platform != "darwin" and _context_has_ca_certs():
        return None

    try:
        import certifi
    except ImportError:
        if verbose and not _context_has_ca_certs():
            print("[ssl] WARNING: no CA certificates available and certifi "
                  "is not installed — https fetches (photos, elevation, "
                  "OSM, address search) will fail. "
                  "Fix: pip install -r requirements.txt",
                  file=sys.stderr)
        return None
    cafile = certifi.where()
    if not (cafile and os.path.isfile(cafile)):
        return None
    os.environ["SSL_CERT_FILE"] = cafile
    if verbose:
        print(f"[ssl] using certifi CA bundle: {cafile}", file=sys.stderr)
    return cafile
