"""
http_utils.py — Shared stdlib JSON-over-HTTP helper.

A single GET-and-parse-JSON helper used by every network fetcher
(``property_data``, ``terrain``, ``climate``, ``wind``). It sets a
User-Agent, applies a timeout, and returns ``None`` on any failure so
callers degrade gracefully when offline rather than crashing.

Each fetcher module keeps a thin ``_http_get_json`` wrapper (with its own
default timeout) so existing tests can still monkeypatch
``<module>._http_get_json`` — but the actual request/parse logic lives
here, in one place, instead of being copy-pasted four ways.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

from src.log import get_logger

log = get_logger(__name__)

#: Where the app can be found, said on every request (V3.31, FN-6).
APP_URL = "https://github.com/yarrowyarrowyarrow/Site-and-Pattern"


def user_agent() -> str:
    """The app's name and version, and where it lives: what OpenStreetMap's
    and Nominatim's usage policies ask an app to send, and what Open-Meteo's
    operators can read when a version misbehaves. The map's tile requests send
    the same string (``map_widget``).

    Until V3.31 it was ``PermaDesign/1.0`` and the pre-rebrand repository,
    kept "for providers' allow-lists"; no provider has an entry for it (the
    app has no keys and no registration), so it only named a product that no
    longer exists and a version that never changed."""
    try:
        from src.app_version import running_version
        version = (running_version() or "dev").lstrip("V")
    except Exception:                                      # noqa: BLE001
        version = "dev"
    return f"SiteAndPattern/{version} (+{APP_URL})"


_USER_AGENT = user_agent()


def http_get_json(url: str, timeout: float = 20.0) -> Optional[dict]:
    """GET a URL and return parsed JSON, or ``None`` on any failure.

    The ``None``-on-failure contract is what every fetcher's offline
    fallback chain is built on — but the failure *classes* are logged
    distinctly so a field log can tell "offline" (INFO, routine) from
    "the server rejected us" or "the payload didn't parse" (WARNING,
    a bug or an API change we should hear about).
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        log.warning("HTTP %s from %s", exc.code, url)
        return None
    except urllib.error.URLError as exc:
        log.info("unreachable (offline?) %s: %s", url, exc.reason)
        return None
    except TimeoutError as exc:
        # Slow public endpoints (SoilGrids especially) time out routinely and
        # every caller has an offline fallback — routine INFO, not a warning
        # on the console of a working app.
        log.info("timed out %s: %s", url, exc)
        return None
    except Exception as exc:  # noqa: BLE001 — transport oddities degrade the same way
        log.warning("fetch failed %s: %s", url, exc)
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        log.warning("non-JSON response from %s: %s", url, exc)
        return None
