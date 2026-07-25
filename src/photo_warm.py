"""
src/photo_warm.py — fill the local photo cache from the seeded image URLs.

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md

Qt-free and stdlib-only, the ``src/image_cache.py`` sibling: that module knows how
to fetch and cache ONE photo, this one knows which photos the catalogue has and
walks them in the background so a card can show a real photograph the first time
it is opened rather than the first time it is opened twice.

The whole catalogue is warmed, not just what is planted: a user browsing a design
clicks plants and creatures they have not placed, the images are small, and the
work happens once per install. Everything about it is defensive — it is a nicety,
never a dependency:

  * already-cached URLs cost nothing (``resolve_image`` checks the cache first),
    so a re-run after a crash resumes rather than restarts;
  * a failed fetch is skipped silently and retried on the next run, matching the
    graceful-degradation contract the rest of the image path already keeps;
  * ``cancel()`` is honoured between items, so closing the window stops it;
  * a courtesy delay separates requests — ~380 of them go to one host.

The caller supplies the rows (``plants``/``fauna`` query results), so this module
opens no database and imports no Qt; ``src/scene3d_window.py`` drives it on a
worker thread.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Iterable, Optional

# Sequential with a courtesy gap: iNaturalist serves these for free, and the
# warmer has no deadline at all — the cards work without it.
DEFAULT_DELAY_S = 0.35


def photo_rows(rows: Iterable[dict]) -> list:
    """``(url, attribution, license)`` for every row that has a photo, de-duped.

    Several species share one observation photo, so the same URL can appear more
    than once; fetching it twice would be pure waste.
    """
    out, seen = [], set()
    for row in rows or ():
        url = (row.get("image_url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append((url, row.get("image_attribution") or "",
                    row.get("image_license") or ""))
    return out


class PhotoWarmer:
    """Walk a list of ``(url, attribution, license)`` and cache each one.

    ``on_progress(done, total, newly_cached)`` is called after each item so the
    caller can re-push its dossier as photos land. It runs on the warming thread,
    so a Qt caller must hop to the UI thread with a signal.
    """

    def __init__(self, items, *, delay_s: float = DEFAULT_DELAY_S,
                 on_progress: Optional[Callable] = None, resolve=None,
                 cancel_event: Optional[threading.Event] = None):
        self._items = list(items or ())
        self._delay_s = delay_s
        self._on_progress = on_progress
        self._resolve = resolve            # injectable for tests
        # A caller that owns the flag can set it before the warmer even exists —
        # closing the 3D window races the worker thread's first query otherwise,
        # and a cancel that lands in that window would be lost.
        self._cancel = cancel_event or threading.Event()
        self.cached = 0
        self.failed = 0

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def run(self) -> dict:
        """Warm every item; returns ``{cached, failed, total, cancelled}``."""
        resolve = self._resolve
        if resolve is None:
            from src.image_cache import resolve_image as resolve   # noqa: PLC0415
        total = len(self._items)
        for i, (url, attribution, license_str) in enumerate(self._items, start=1):
            if self._cancel.is_set():
                break
            got = None
            try:
                got = resolve(url, attribution, license_str)
            except Exception:              # noqa: BLE001 — never a dependency
                got = None
            if got:
                self.cached += 1
            else:
                self.failed += 1
            if self._on_progress:
                try:
                    self._on_progress(i, total, bool(got))
                except Exception:          # noqa: BLE001
                    pass
            # Wait on the cancel event rather than sleeping, so closing the
            # window stops the warmer immediately instead of after the gap.
            if self._delay_s > 0 and i < total:
                self._cancel.wait(self._delay_s)
        return {"cached": self.cached, "failed": self.failed, "total": total,
                "cancelled": self._cancel.is_set()}


def catalogue_photo_rows(queries=None) -> list:
    """Every seeded plant + fauna photo, ready for :class:`PhotoWarmer`.

    ``queries`` is an iterable of zero-argument row sources, injectable so this
    stays testable without a database; the default pair is the ordinary read APIs.
    A query that raises contributes nothing rather than sinking the warmer.
    """
    if queries is None:
        from src.db.fauna import list_fauna         # noqa: PLC0415
        from src.db.plants import get_all_plants    # noqa: PLC0415
        queries = (get_all_plants, list_fauna)
    rows = []
    for query in queries:
        try:
            rows.extend(query() or [])
        except Exception:                           # noqa: BLE001
            continue
    return photo_rows(rows)
