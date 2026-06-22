"""
src/github_releases.py — GitHub Releases lookup for the in-app updater.

Qt-free and dependency-free (stdlib ``urllib`` + ``json``) so it can be
unit-tested without PyQt6 and imported by any layer. The Qt-aware
download/progress UI lives in ``src/controllers/update_flow.py``.

Why this exists
---------------
A *frozen* build (the ``.dmg`` / ``.exe`` that friends run) has no git
checkout, so the updater can't ``git pull`` new source into itself — the
Python code is packed inside the bundle. Instead it asks the GitHub
Releases API which versions have a published installer, compares against the
version baked into the build (``src/app_version.py`` → ``version.txt``), and
downloads the matching asset.

Release tags follow the same ``V<major>.<minor>`` convention as the branches
(see CLAUDE.md) — the GitHub Actions release workflow tags each release with
the branch name. Tag parsing here is deliberately a touch more lenient than
``src/version_branch.parse_version_branch`` — it also accepts a lowercase
leading ``v`` (the historical ``v1.64`` release) — but the ``(major, minor)``
ordering is identical, so the two stay consistent.

Network note: ``src/ssl_bootstrap.ensure_ca_bundle`` (run at startup) points
OpenSSL at certifi's CA bundle, so the https calls here verify correctly in
frozen builds that ship no system certificates.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

# The canonical repo slug for the Releases API. The repo was renamed from
# "PermaDesign" to "Site-and-Pattern"; GitHub redirects the old name, but we
# target the current name directly so the updater never depends on a redirect.
DEFAULT_REPO = "yarrowyarrowyarrow/Site-and-Pattern"

_API_BASE = "https://api.github.com"
_USER_AGENT = "SiteAndPattern-Updater"

_TAG_RE = re.compile(r"^[vV]?(\d+)\.(\d+)$")


class DownloadCancelled(Exception):
    """Raised by :func:`download_asset` when the progress callback asks to
    stop (returns ``False``)."""


def parse_release_version(tag: str) -> Optional[Tuple[int, int]]:
    """Return ``(major, minor)`` for a release tag, else ``None``.

    Accepts ``V1.72``, ``v1.64`` and bare ``1.5`` — anything else (``main``,
    ``V1``, ``1.2.3``) is rejected so non-release tags never sort into the
    version list."""
    if not tag:
        return None
    m = _TAG_RE.match(tag.strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


@dataclass(frozen=True)
class Asset:
    """A single downloadable file attached to a release."""
    name: str
    download_url: str
    size: int


@dataclass(frozen=True)
class Release:
    tag: str
    version: Tuple[int, int]
    name: str
    body: str
    html_url: str
    prerelease: bool
    assets: Tuple[Asset, ...]

    def asset_for_extensions(self, extensions: Sequence[str]) -> Optional[Asset]:
        """First asset whose filename ends with one of ``extensions`` (case-
        insensitive), preferring the order given (so ``(\".exe\", \".zip\")``
        picks the installer over the zip fallback)."""
        lowered = [e.lower() for e in extensions]
        for ext in lowered:
            for a in self.assets:
                if a.name.lower().endswith(ext):
                    return a
        return None


def platform_asset_extensions(platform: Optional[str] = None) -> Tuple[str, ...]:
    """Installer file extensions to look for on a given platform, most
    preferred first. Defaults to the running platform."""
    p = platform or sys.platform
    if p == "darwin":
        return (".dmg",)
    if p.startswith("win"):
        return (".exe", ".zip")
    return (".appimage", ".zip", ".tar.gz")


def _default_fetch_json(url: str, timeout: float = 15.0) -> object:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT,
                 "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        return json.loads(resp.read().decode("utf-8"))


def list_releases(
    repo: str = DEFAULT_REPO,
    *,
    include_prereleases: bool = False,
    fetch_json: Callable[[str], object] = _default_fetch_json,
) -> List[Release]:
    """Published releases whose tag parses as a version, newest first.

    Drafts are always skipped; prereleases are skipped unless
    ``include_prereleases``. ``fetch_json`` is injectable for tests."""
    url = f"{_API_BASE}/repos/{repo}/releases?per_page=100"
    data = fetch_json(url)
    if not isinstance(data, list):
        return []
    releases: List[Release] = []
    for item in data:
        if not isinstance(item, dict) or item.get("draft"):
            continue
        if item.get("prerelease") and not include_prereleases:
            continue
        version = parse_release_version(item.get("tag_name") or "")
        if version is None:
            continue
        assets = tuple(
            Asset(
                name=a.get("name") or "",
                download_url=a.get("browser_download_url") or "",
                size=int(a.get("size") or 0),
            )
            for a in (item.get("assets") or [])
            if isinstance(a, dict) and a.get("browser_download_url")
        )
        releases.append(
            Release(
                tag=item.get("tag_name") or "",
                version=version,
                name=item.get("name") or item.get("tag_name") or "",
                body=item.get("body") or "",
                html_url=item.get("html_url") or "",
                prerelease=bool(item.get("prerelease")),
                assets=assets,
            )
        )
    releases.sort(key=lambda r: r.version, reverse=True)
    return releases


def latest_release(
    repo: str = DEFAULT_REPO,
    *,
    include_prereleases: bool = False,
    fetch_json: Callable[[str], object] = _default_fetch_json,
) -> Optional[Release]:
    """The newest published release, or ``None`` if there are none."""
    rels = list_releases(
        repo, include_prereleases=include_prereleases, fetch_json=fetch_json
    )
    return rels[0] if rels else None


def download_asset(
    asset: Asset,
    dest_path: str,
    *,
    progress: Optional[Callable[[int, int], object]] = None,
    opener: Callable[..., object] = urllib.request.urlopen,
    chunk_size: int = 1 << 16,
    timeout: float = 60.0,
) -> str:
    """Stream ``asset`` to ``dest_path``, returning the path on success.

    Downloads to a ``.part`` sidecar first and atomically renames on
    completion, so a cancelled/failed download never leaves a half file that
    looks valid. ``progress(downloaded, total)`` is called as bytes arrive;
    returning ``False`` cancels (raises :class:`DownloadCancelled`).
    ``opener`` is injectable for tests.

    NOTE: because *the app itself* fetches the file (not a browser), macOS
    does not stamp it with ``com.apple.quarantine`` — so the downloaded
    installer launches without the Gatekeeper warning the first manual
    download triggers.
    """
    req = urllib.request.Request(
        asset.download_url, headers={"User-Agent": _USER_AGENT}
    )
    part_path = dest_path + ".part"
    resp = opener(req, timeout=timeout)
    try:
        headers = getattr(resp, "headers", None)
        clen = None
        if headers is not None:
            try:
                clen = headers.get("Content-Length")
            except AttributeError:
                clen = None
        total = int(clen) if clen else int(asset.size or 0)
        downloaded = 0
        with open(part_path, "wb") as out:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if progress is not None and progress(downloaded, total) is False:
                    raise DownloadCancelled()
    except BaseException:
        # Clean up the partial file on cancel/error.
        try:
            os.remove(part_path)
        except OSError:
            pass
        raise
    finally:
        close = getattr(resp, "close", None)
        if callable(close):
            close()
    os.replace(part_path, dest_path)
    return dest_path
