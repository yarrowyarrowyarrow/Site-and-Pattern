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
import re
import tempfile
import threading
import urllib.error
import urllib.request
from typing import Optional

_CACHE_DIRNAME = "image_cache"
_META_FILENAME = "image_metadata.json"
_EXT_BY_CTYPE = {
    "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp",
    "image/jpeg": ".jpg", "image/jpg": ".jpg",
}

# The metadata index is one JSON file shared by every surface that shows a photo
# (plant browser, analysis galleries, the 3D dossier card, the Field Study quiz)
# and written from worker threads. It therefore needs BOTH halves of write
# safety, and used to have neither:
#
#   * a lock, because the update is read-modify-write — two threads that both
#     load, both add their own entry, and both save keep only the last one's
#     work. With the quiz starting eight fetches at once, most warmed photos
#     never reached the index at all, which is why the identify pool visibly
#     failed to grow the way the code above it promises.
#   * an atomic replace, because `open(path, "w")` truncates first, so a reader
#     arriving mid-write saw a half-written file, failed to parse it, and got
#     back "no cache" — a photo silently missing rather than merely not fetched
#     yet, and non-deterministically so.
#
# `_META_LOCK` serialises writes within the process and `os.replace` makes each
# one atomic for readers, so a reader now sees either the old file or the new
# one and never a torn one.
_META_LOCK = threading.RLock()

# Parsed metadata memoised against (path, mtime, size). Reads outnumber writes
# by orders of magnitude — one quiz round asks "is there a photo for this
# plant?" for every plant in the catalogue, which was ~1,900 full parses of a
# 76 KB file on the UI thread, about half a second of blocking work that grew as
# the cache filled. Keying on the path (not just the stamp) keeps tests that
# redirect the data dir from reading each other's index.
_meta_cache: Optional[dict] = None
_meta_stamp: Optional[tuple] = None

# Directories we have already created this process, so the read path stops
# issuing a mkdir syscall per lookup alongside the parse it no longer does.
_made_dirs: set[str] = set()


def _cache_dir() -> pathlib.Path:
    from src.db.plants import _user_data_dir
    cache = pathlib.Path(_user_data_dir()) / _CACHE_DIRNAME
    key = str(cache)
    # `is_dir()` re-checks cheaply so a directory removed underneath us (tests
    # do this) is recreated rather than assumed.
    if key not in _made_dirs or not cache.is_dir():
        cache.mkdir(parents=True, exist_ok=True)
        _made_dirs.add(key)
    return cache


def _meta_path() -> pathlib.Path:
    return _cache_dir() / _META_FILENAME


def _meta_key(p: pathlib.Path) -> Optional[tuple]:
    """``(path, mtime, size)`` for the memo, or ``None`` if the file is gone."""
    try:
        st = p.stat()
    except OSError:
        return None
    return (str(p), st.st_mtime_ns, st.st_size)


def _load_meta() -> dict:
    """The metadata index, parsed at most once per on-disk revision.

    Callers must treat the result as read-only — it may be the shared memo.
    Use :func:`_remember` to add an entry.
    """
    global _meta_cache, _meta_stamp
    p = _meta_path()
    stamp = _meta_key(p)
    if stamp is None:
        with _META_LOCK:
            _meta_cache, _meta_stamp = None, None
        return {}
    with _META_LOCK:
        if _meta_stamp == stamp and _meta_cache is not None:
            return _meta_cache
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError):
        # ValueError covers JSONDecodeError and, should this ever be written
        # with ensure_ascii=False, UnicodeDecodeError too. Reading the index
        # must always degrade to "no cache" rather than propagate: several
        # callers run on a paint path or inside a Qt slot, where an escaping
        # exception is a process abort, not a stack trace.
        return {}
    if not isinstance(data, dict):
        return {}
    with _META_LOCK:
        _meta_cache, _meta_stamp = data, stamp
    return data


def _write_meta_locked(meta: dict) -> None:
    """Replace the index atomically. Caller holds ``_META_LOCK``."""
    global _meta_cache, _meta_stamp
    p = _meta_path()
    tmp = ""
    try:
        fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".meta-",
                                   suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
        tmp = ""
    except OSError:
        return  # graceful — a photo credit is not worth an exception
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    _meta_cache, _meta_stamp = meta, _meta_key(p)


def _save_meta(meta: dict) -> None:
    """Write the whole index. Prefer :func:`_remember` for a single entry —
    this one still clobbers concurrent additions, it just no longer tears."""
    with _META_LOCK:
        _write_meta_locked(dict(meta))


def _remember(url: str, entry: dict) -> None:
    """Merge one entry into the index without losing a concurrent writer's."""
    with _META_LOCK:
        meta = dict(_load_meta())
        meta[url] = entry
        _write_meta_locked(meta)


def _is_local_file(url: str) -> bool:
    return bool(url) and "://" not in url and os.path.exists(url)


def cache_key(url: str) -> str:
    """Stable opaque handle for a photo's cache entry.

    The same sha256 stem :func:`fetch_and_cache_image` names files with, exposed
    so a consumer can *address* a cached image without holding its URL. That is
    what lets the 3D viewer show a photo: the loopback server resolves a key
    inside the cache directory only (``web_assets`` ``/__image``), so no remote
    URL ever reaches the browser and nothing outside the cache is addressable.
    """
    return hashlib.sha256((url or "").encode("utf-8")).hexdigest()[:16]


def cached_path_for_key(key: str) -> Optional[str]:
    """Local path for a :func:`cache_key`, or ``None``. Never touches the
    network, and never returns anything outside the cache directory."""
    if not key or not key.isalnum():
        return None
    cache = _cache_dir()
    for entry in _load_meta().values():
        filename = entry.get("filename", "")
        if filename and os.path.splitext(filename)[0] == key:
            p = cache / filename
            if p.exists():
                return str(p)
    return None


def credit_line(attribution: str = "", license_str: str = "") -> str:
    """The one-line photo credit, formatted the same way everywhere.

    Showing an open-licensed photo obliges us to show who made it and under what
    licence; three call sites used to build this string separately, dropping the
    licence, which is how a credit goes missing from one of them.

    The licence is appended only when the attribution does not already name one.
    iNaturalist's attribution reads "(c) Someone, some rights reserved (CC BY),
    uploaded by Someone", so pasting the ``cc-by`` slug after it says the same
    thing twice in two notations.
    """
    attribution = (attribution or "").strip()
    license_str = (license_str or "").strip()
    if attribution and license_str and _names_a_licence(attribution):
        license_str = ""
    return " · ".join(p for p in (attribution, license_str) if p)


# Enough to recognise "this text already states the licence". Deliberately broad:
# a doubled credit is cosmetic, a missing one is a licence violation, so anything
# uncertain falls through to appending the slug.
_LICENCE_WORDS = ("cc0", "public domain", "creative commons")


def _names_a_licence(text: str) -> bool:
    low = text.lower()
    if any(w in low for w in _LICENCE_WORDS):
        return True
    # "CC BY", "CC BY-SA", "CC-BY-NC" … — 'cc' followed by a licence letter code.
    return bool(re.search(r"\bcc[\s-]?(by|nd|sa|nc|zero)\b", low))


def get_cached_image(url: str) -> Optional[str]:
    """Local path for ``url`` if it's already available (a real local file, or a
    previously-cached download), else ``None``. Never touches the network — safe
    to call from a paint path.

    "Safe" is enforced here rather than trusted at each call site: this is
    reached from paint paths and from Qt slots (the analysis galleries, the
    plant-list delegate, the quiz), and an exception escaping a slot aborts the
    process instead of raising. A cache lookup has no failure worth propagating
    — "no photo" is always a valid answer.
    """
    if not url:
        return None
    try:
        if _is_local_file(url):
            return url
        entry = _load_meta().get(url)
        if entry:
            p = _cache_dir() / entry.get("filename", "")
            if p.exists():
                return str(p)
    except Exception:      # noqa: BLE001 — see the docstring
        return None
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
        # A descriptive User-Agent — some hosts (incl. iNaturalist) reject the
        # default urllib agent with HTTP 403.
        req = urllib.request.Request(
            url, headers={"User-Agent": "PermaDesign (native habitat design app)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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
    _remember(url, {"filename": filename,
                    "attribution": attribution, "license": license_str})
    return str(_cache_dir() / filename)


def resolve_image(url: str, attribution: str = "", license_str: str = "",
                  fetch_if_missing: bool = True) -> Optional[str]:
    """Resolve ``url`` to a local path: cache/local first, then (optionally)
    fetch+cache. Returns ``None`` if unavailable."""
    cached = get_cached_image(url)
    if cached or not fetch_if_missing:
        return cached
    return fetch_and_cache_image(url, attribution, license_str)
