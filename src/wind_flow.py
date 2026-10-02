"""
wind_flow.py — orchestration for fetching site wind data (V1.67).

Free functions taking ``main`` (kept off MainWindow/controller, like
``building_flow``/``splat_flow``). Pulls the seasonal wind rose
(``wind.get_wind_summary``, DB-cached → offline after first fetch) plus the live
current reading off the UI thread, and hands them to the Wind page. Falls back
to a bundled regional approximation (``data/wind_fallback_prairie.json``) when
offline with nothing cached, mirroring the rainfall/soil fallbacks.

**Wind comes with the pin (V3.07).** The Site panel's fetch has read the rose
with every pin since V2.13, for one line on Site Info, and the Wind page never
saw it: it waited for its own button and fetched the same rose again. The
owner said yes to fetching it with the pin's other site data on the V3.05
surface audit, so :func:`on_site_wind` fills the page from the pin's rose, and
:func:`show_cached` from the local cache when a design is opened. The page's
Refresh is :func:`fetch_wind_for_site`, which adds the reading of the wind now.
"""

from __future__ import annotations

import json
import math

from src import wind


def _dist2(a, b) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _fallback_rose(lat: float, lng: float):
    """Synthesize an approximate rose from the nearest bundled regional
    prevailing wind, so a fully-offline first run still shows something useful."""
    from src.resources import resource_path
    try:
        with open(resource_path("data", "wind_fallback_prairie.json"),
                  encoding="utf-8") as f:
            entries = json.load(f)
    except Exception:  # noqa: BLE001
        return None
    if not entries:
        return None
    best = min(entries, key=lambda e: _dist2((lat, lng),
                                             tuple(e.get("centroid") or (0, 0))))
    deg = float(best.get("prevailing_deg", 270))
    spd = float(best.get("mean_speed_kmh", 14))
    # 10 hours/month at the regional prevailing dir/speed → a real rose shape.
    rows = [{"month": m, "dir_deg": deg, "speed": spd}
            for m in range(1, 13) for _ in range(10)]
    rose = wind.compute_wind_rose(rows)
    rose["cached"] = False
    rose["approximate"] = True
    rose["source"] = f"Regional approximation — {best.get('region', 'prairie')}"
    return rose


def _site_latlng(main):
    sc = (main._project.get("properties", {}) or {}).get("site_config", {}) or {}
    lat, lng = sc.get("latitude"), sc.get("longitude")
    if lat is None or lng is None:
        c = getattr(main.map_widget, "_last_center", None)
        if c:
            lat, lng = c
    return lat, lng


def _apply(main, result: dict, *, persist: bool = True) -> None:
    """Show a rose (and the wind now, when there is a reading) on the Wind page
    and Site Info's one line, and keep the prevailing wind on the design
    (``persist``), where the generator and the 3D scene read it."""
    rose = result.get("rose")
    main.analysis_panel.set_wind_data(rose, result.get("current"))
    if rose:
        try:
            main.site_panel.show_wind(rose)
        except Exception:  # noqa: BLE001 — a panel without the row
            pass
    advice = wind.windbreak_advice(rose) if rose else None
    if rose and persist:
        a = rose.get("annual") or {}
        sc = (main._project.setdefault("properties", {})
              .setdefault("site_config", {}))
        sc["wind_prevailing_deg"] = a.get("prevailing_deg")
        sc["wind_mean_kmh"] = a.get("mean_speed")
        sc["wind_exposure"] = ("exposed" if (advice and advice["exposed"])
                               else "moderate")
        try:
            main._mark_modified()
        except Exception:  # noqa: BLE001
            pass
    if advice:
        main.analysis_panel.set_wind_advice(advice["text"])


def on_site_wind(main, rose) -> None:
    """The pin's fetch read the rose: fill the Wind page from it, without a
    second fetch. Offline with nothing cached, the regional approximation, as
    Refresh gives."""
    if not rose:
        lat, lng = _site_latlng(main)
        rose = (_fallback_rose(lat, lng)
                if lat is not None and lng is not None else None)
    if rose:
        _apply(main, {"rose": rose, "current": None})


def show_cached(main, lat: float, lng: float) -> None:
    """A design opened with a pin and its site data cached: the rose from the
    local cache, with no network and nothing written to the design (opening
    one must not mark it changed). Nothing cached shows nothing."""
    try:
        from src.db.plants import get_cached_wind
        rose = get_cached_wind(lat, lng)
    except Exception:  # noqa: BLE001
        rose = None
    if rose:
        rose["cached"] = True
        _apply(main, {"rose": rose, "current": None}, persist=False)


def fetch_wind_for_site(main) -> None:
    """Fetch the wind rose + current reading for the site, off-thread, and push
    them into the Wind tab. No-op with a status note when no location is set."""
    lat, lng = _site_latlng(main)
    if lat is None or lng is None:
        main.analysis_panel.set_wind_status(
            "Drop a property pin or set a location first.")
        return
    main.analysis_panel.set_wind_status("Fetching wind data…")

    from PyQt6.QtCore import QThread
    thread = QThread(main)
    worker = _WindFetchWorker(lat, lng)
    worker.moveToThread(thread)
    main._wind_thread = thread
    main._wind_worker = worker

    def _done():
        worker.deleteLater()
        thread.deleteLater()
        main._wind_worker = None
        main._wind_thread = None

    thread.started.connect(worker.run)
    worker.done.connect(lambda result: _apply(main, result))
    worker.done.connect(thread.quit)
    thread.finished.connect(_done)
    thread.start()


try:
    from PyQt6.QtCore import QObject, pyqtSignal
    _HAVE_QT = True
except ImportError:  # pragma: no cover
    _HAVE_QT = False

if _HAVE_QT:
    class _WindFetchWorker(QObject):
        done = pyqtSignal(object)     # {"rose": dict|None, "current": dict|None}

        def __init__(self, lat, lng):
            super().__init__()
            self._lat = lat
            self._lng = lng

        def run(self):
            try:
                rose = wind.get_wind_summary(self._lat, self._lng)
            except Exception:  # noqa: BLE001
                rose = None
            if rose is None:
                rose = _fallback_rose(self._lat, self._lng)
            try:
                current = wind.fetch_current_wind(self._lat, self._lng)
            except Exception:  # noqa: BLE001
                current = None
            self.done.emit({"rose": rose, "current": current})
