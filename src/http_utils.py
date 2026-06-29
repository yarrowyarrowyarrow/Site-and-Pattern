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
import urllib.request
from typing import Optional

# Legacy product identifier, retained intentionally (see CLAUDE.md: User-Agent
# strings deliberately keep the pre-rebrand "PermaDesign" name).
_USER_AGENT = "PermaDesign/1.0 (https://github.com/yarrowyarrowyarrow/permadesign)"


def http_get_json(url: str, timeout: float = 20.0) -> Optional[dict]:
    """GET a URL and return parsed JSON, or ``None`` on any failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
