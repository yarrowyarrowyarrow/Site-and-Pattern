"""
src/image_cache.py — local cache + resolver for flora/fauna photos (I1).

Qt-free, stdlib-only (urllib), mirroring the graceful-degradation pattern in
``src/climate.py``: a missing or unreachable image returns ``None`` instead of
raising, so the UI simply shows no photo. Open-licensed image URLs (Wikimedia
Commons / iNaturalist / …) are fetched once and cached under the user-data dir;
the attribution + license travel with the cached file in a small JSON sidecar so
the citation can always be shown beside the photo.

The UI should call :func:`get_cached_image` on the paint path (cache-only, never
blocks) and :func:`resolve_image` off the paint path (e.g. when a row expands) to
populate the cache.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import urllib.error
import urllib.request
from typing import Optional

_CACHE_DIRNAME = "image_cache"
_META_FILENAME = "image_metadata.json"
_EXT_BY_CTYPE = {
    "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp",
    "image/jpeg": ".jpg", "image/jpg": ".jpg",
}


def _cache_dir() -> pathlib.Path:
    from src.db.plants import _user_data_dir
    cache = pathlib.Path(_user_data_dir()) / _CACHE_DIRNAME
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def _meta_path() -> pathlib.Path:
    return _cache_dir() / _META_FILENAME


def _load_meta() -> dict:
    p = _meta_path()
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_meta(meta: dict) -> None:
    try:
        with open(_meta_path(), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
    except OSError:
        pass  # graceful


def _is_local_file(url: str) -> bool:
    return bool(url) and "://" not in url and os.path.exists(url)


def get_cached_image(url: str) -> Optional[str]:
    """Local path for ``url`` if it's already available (a real local file, or a
    previously-cached download), else ``None``. Never touches the network — safe
    to call from a paint path."""
    if not url:
        return None
    if _is_local_file(url):
        return url
    entry = _load_meta().get(url)
    if entry:
        p = _cache_dir() / entry.get("filename", "")
        if p.exists():
            return str(p)
    return None


def fetch_and_cache_image(url: str, attribution: str = "", license_str: str = "",
                          timeout: float = 10.0) -> Optional[str]:
    """Download ``url`` to the cache and record its attribution/license. Returns
    the local path, or ``None`` on any failure. A local file path is returned
    as-is. Already-cached URLs are served from cache."""
    if not url:
        return None
    if _is_local_file(url):
        return url
    cached = get_cached_image(url)
    if cached:
        return cached
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = resp.read()
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
    except (urllib.error.URLError, urllib.error.HTTPError,
            TimeoutError, ValueError, OSError):
        return None
    if not data:
        return None
    ext = _EXT_BY_CTYPE.get(ctype.lower(), os.path.splitext(url)[1] or ".jpg")
    filename = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16] + ext
    try:
        with open(_cache_dir() / filename, "wb") as f:
            f.write(data)
    except OSError:
        return None
    meta = _load_meta()
    meta[url] = {"filename": filename,
                 "attribution": attribution, "license": license_str}
    _save_meta(meta)
    return str(_cache_dir() / filename)


def resolve_image(url: str, attribution: str = "", license_str: str = "",
                  fetch_if_missing: bool = True) -> Optional[str]:
    """Resolve ``url`` to a local path: cache/local first, then (optionally)
    fetch+cache. Returns ``None`` if unavailable."""
    cached = get_cached_image(url)
    if cached or not fetch_if_missing:
        return cached
    return fetch_and_cache_image(url, attribution, license_str)
